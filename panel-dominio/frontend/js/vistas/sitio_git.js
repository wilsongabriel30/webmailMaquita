// Pestaña «Git»: desplegar el sitio PHP desde un repositorio (rama, autenticación, botón «Desplegar», gancho para
// desplegar con cada push, registro y vuelta a una versión anterior). El despliegue corre en el servidor en segundo
// plano: la pestaña consulta el estado cada pocos segundos hasta que termina.
import { api } from '../api.js';
import { el, agregar, aviso, campo } from '../ui.js';
import { confirmar, enRutaSitio, hacer, mensajes, unaVez } from './sitio_comun.js';
import { cajaAutenticacion } from './sitio_git_autenticacion.js';

const ORIGEN = { panel: 'Desde el portal', gancho: 'Por un push', volver: 'Vuelta atrás' };
const corto = (c) => (c ? String(c).slice(0, 8) : '—');

function formulario(ruta, g, msj, alGuardar) {
  const repo = campo('Repositorio', { type: 'text', maxlength: 400, valor: g.repo || '', required: true, autocomplete: 'off',
    placeholder: 'git@servidor:organizacion/sitio.git' }, 'Por SSH o https://. Si es privado, elige en «Autenticación» cómo entra el servidor (mejor: clave de despliegue de solo lectura).');
  const rama = campo('Rama', { type: 'text', maxlength: 100, valor: g.rama || 'main' });
  const carpeta = campo('Carpeta del repositorio que se publica', { type: 'text', maxlength: 300, valor: g.carpeta || '', placeholder: 'vacío = todo el repositorio' });
  const raiz = campo('Carpeta que sirve la web', { type: 'text', maxlength: 300, valor: g.raiz_web || '', placeholder: 'p. ej. public (Laravel, Symfony)' },
    'Lo que quede fuera de ella (código, .env) no se ve desde internet.');
  const exclusiones = el('textarea', { rows: '3', 'aria-label': 'Archivos y carpetas que el despliegue no toca', valor: (g.exclusiones || []).join('\n'),
    placeholder: 'wp-content/uploads\nstorage\n.env' });
  const boton = el('button', { clase: 'boton', type: 'submit' }, g.configurado ? 'Guardar cambios' : 'Configurar');
  const form = el('form', { alSubmit: async (e) => {
    e.preventDefault();
    const datos = { repo: repo.entrada.value.trim(), rama: rama.entrada.value.trim(), carpeta: carpeta.entrada.value.trim(),
      raiz_web: raiz.entrada.value.trim(), exclusiones: exclusiones.value.split('\n').map(x => x.trim()).filter(Boolean) };
    const r = await hacer(msj, boton, 'Guardando…', () => api.put(ruta, datos));
    if (r) alGuardar('Configuración guardada.');
  } },
    el('div', { clase: 'rejilla' }, repo.nodo, rama.nodo, carpeta.nodo, raiz.nodo),
    el('label', null, 'Archivos y carpetas que el despliegue no toca (uno por línea)'), exclusiones,
    el('p', { clase: 'ayuda' }, `Lo subido por la aplicación (imágenes, adjuntos) va aquí: ni se borra ni se pisa. Siempre se conservan ${(g.exclusiones_fijas || ['.well-known']).join(', ')}.`),
    el('div', { clase: 'pie-form' }, boton));
  form.repo = repo.entrada;
  return form;
}

function filaDespliegue(d) {
  return el('tr', null, el('td', null, d.inicio || ''), el('td', null, ORIGEN[d.origen] || d.origen),
    el('td', null, el('span', { clase: 'marca ' + (d.estado === 'ok' ? 'si' : d.estado === 'error' ? 'no' : 'aviso-marca') },
      d.estado === 'ok' ? 'Bien' : d.estado === 'error' ? 'Falló' : 'En curso')),
    el('td', null, el('code', null, corto(d.commit)), d.mensaje ? el('div', { clase: 'ayuda' }, d.mensaje) : null,
      d.error ? el('div', { clase: 'ayuda' }, d.error) : null),
    el('td', null, d.segundos !== undefined ? `${d.segundos} s` : ''));
}

export async function pestanaGit(ctx, mensaje) {
  const ruta = `/sitios/${enRutaSitio(ctx.sitio)}/git`;
  const g = await api.get(ruta);
  const raiz = el('div');
  const msj = mensajes();
  const recargar = async (texto) => raiz.replaceWith(await pestanaGit(ctx, texto));
  if (!g.configurado && !g.compatible) {
    return aviso('nota', `El despliegue desde git no está disponible para este sitio: ${g.motivo}.`);
  }
  if (!g.configurado) {
    const nuevo = formulario(ruta, g, msj, recargar);
    return agregar(raiz, el('h2', null, 'Desplegar desde git'),
      el('p', { clase: 'ayuda' }, 'Cada despliegue trae la rama del repositorio y la publica en el sitio: lo que ya no está en el repositorio se borra (salvo lo que indiques abajo). Antes del primero se guarda una copia del sitio.'),
      msj.nodo, nuevo, await cajaAutenticacion(ctx, () => nuevo.repo.value));
  }
  const esperar = async () => {
    for (let i = 0; i < 400; i++) {
      await new Promise(r => setTimeout(r, 3000));
      if (!raiz.isConnected) return undefined;  // se cambió de pestaña: deja de preguntar
      const e = await api.get(ruta).catch(() => null);
      if (e && !e.en_curso) return recargar(e.despliegues[0] && e.despliegues[0].estado === 'ok' ? 'Despliegue terminado.' : 'El despliegue terminó con un error: mira el registro.');
    }
    return recargar();
  };
  const desplegar = el('button', { clase: 'boton', type: 'button', disabled: g.en_curso }, g.en_curso ? 'Desplegando…' : 'Desplegar ahora');
  desplegar.addEventListener('click', async () => {
    if (await hacer(msj, desplegar, 'Iniciando el despliegue…', () => api.post(ruta + '/desplegar'))) {
      desplegar.disabled = true;
      msj.espera('Desplegando: trayendo la rama y publicándola. Puedes dejar esta pestaña abierta.');
      esperar();
    }
  });
  const gancho = el('button', { clase: 'boton claro', type: 'button' }, g.gancho ? 'Cambiar el secreto' : 'Activar el gancho');
  gancho.addEventListener('click', async () => {
    const r = await hacer(msj, gancho, 'Generando el secreto…', () => api.post(ruta + '/gancho', { accion: 'activar' }));
    if (!r) return;
    unaVez('Gancho para desplegar con cada push', [
      { etiqueta: 'Dirección (URL del webhook)', valor: `https://${location.hostname}${r.gancho_ruta}` },
      { etiqueta: 'Secreto', valor: r.secreto, secreto: true },
      { etiqueta: 'Tipo de contenido', valor: 'application/json' },
      { etiqueta: 'Eventos', valor: `Solo push (despliega la rama ${r.rama})` },
    ], 'Ponlos en el servidor de git (GitHub, Gitea, Forgejo: «Webhooks»; GitLab: el secreto va como «Secret token»). El secreto no se vuelve a mostrar.');
    recargar('Gancho activo.');
  });
  const apagar = g.gancho ? el('button', { clase: 'enlace peligro', type: 'button' }, 'Desactivar') : null;
  if (apagar) apagar.addEventListener('click', async () => {
    if (await hacer(msj, apagar, 'Desactivando…', () => api.post(ruta + '/gancho', { accion: 'desactivar' }))) recargar('Gancho desactivado.');
  });
  const versiones = (g.versiones || []).slice().reverse().map(v => {
    const b = v.id === g.actual ? el('span', { clase: 'marca si' }, 'Publicada') : el('button', { clase: 'enlace', type: 'button' }, 'Volver a esta');
    if (v.id !== g.actual) b.addEventListener('click', async () => {
      if (!await confirmar('Volver a otra versión', `¿Publicar otra vez la versión del ${v.fecha} (${corto(v.commit)})?`, 'Volver')) return;
      if (await hacer(msj, b, 'Publicando esa versión…', () => api.post(ruta + '/volver', { version: v.id }))) recargar('Versión publicada.');
    });
    return el('li', null, el('div', null, el('strong', null, v.fecha), ' ', el('code', null, corto(v.commit)), v.mensaje ? el('div', { clase: 'ayuda' }, v.mensaje) : null), b);
  });
  const quitar = el('button', { clase: 'boton peligro', type: 'button' }, 'Quitar el despliegue desde git');
  quitar.addEventListener('click', async () => {
    if (!await confirmar('Quitar git', 'Se borran la configuración, la clave, el gancho y las versiones guardadas. Lo publicado se queda como está.', 'Quitar', true)) return;
    if (await hacer(msj, quitar, 'Quitando…', () => api.del(`${ruta}?confirmacion=${encodeURIComponent(ctx.sitio)}`))) recargar('Despliegue desde git quitado.');
  });
  if (g.en_curso) setTimeout(esperar, 0);
  return agregar(raiz,
    mensaje ? aviso('ok', mensaje) : null,
    el('div', { clase: 'fila' }, el('div', { clase: 'crece' }, el('h2', null, 'Desplegar desde git'),
      el('p', { clase: 'ayuda' }, el('code', null, g.repo), ' · rama ', el('code', null, g.rama))), desplegar),
    msj.nodo,
    await cajaAutenticacion(ctx, () => g.repo),
    el('details', { clase: 'caja' }, el('summary', null, 'Gancho (desplegar con cada push) · ' + (g.gancho ? 'activo' : 'apagado')),
      el('p', { clase: 'ayuda' }, `Dirección: https://${location.hostname}${g.gancho_ruta}. Solo despliega un push firmado con el secreto a la rama ${g.rama}.`),
      el('div', { clase: 'fila' }, gancho, apagar)),
    el('details', { clase: 'caja' }, el('summary', null, 'Configuración'), formulario(ruta, g, msj, recargar)),
    el('h2', null, 'Versiones guardadas'),
    versiones.length ? el('ul', { clase: 'miembros' }, versiones) : el('p', { clase: 'ayuda' }, 'Todavía no se ha desplegado.'),
    el('h2', null, 'Registro'),
    el('div', { clase: 'caja tabla-marco' }, el('table', null,
      el('thead', null, el('tr', null, ['Inicio', 'Origen', 'Resultado', 'Commit', 'Duración'].map(t => el('th', null, t)))),
      el('tbody', null, (g.despliegues || []).length ? g.despliegues.map(filaDespliegue)
        : el('tr', null, el('td', { colspan: '5', clase: 'vacio' }, 'Sin despliegues todavía.'))))),
    el('div', { clase: 'pie-form' }, quitar));
}
