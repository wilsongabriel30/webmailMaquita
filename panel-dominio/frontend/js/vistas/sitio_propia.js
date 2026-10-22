// Pestaña «Node.js y Python»: aplicaciones propias (también estáticas), como en el panel general. Corren con el
// usuario del sitio, encerradas y con límites (memoria, CPU y tareas), y solo escuchan dentro del servidor: nginx las
// publica. Abrir un puerto público lo hace solo el administrador general.
import { api } from '../api.js';
import { el, agregar, aviso, campo, casilla, lista } from '../ui.js';
import { confirmar, enRutaSitio, hacer, mensajes, nombreApp } from './sitio_comun.js';

const TIPOS = [{ valor: 'node', texto: 'Node.js' }, { valor: 'python', texto: 'Python (WSGI o ASGI)' }, { valor: 'estatico', texto: 'Estática (HTML, CSS y JavaScript)' }];
const ACTIVO = { active: ['si', 'En marcha'], inactive: ['no', 'Detenida'], failed: ['no', 'Con errores'], activating: ['aviso-marca', 'Arrancando'], nginx: ['si', 'La sirve nginx'] };

function crear(ctx, ruta, msj, alCrear) {
  const tipo = lista('Tipo', TIPOS);
  const git = campo('Repositorio git (opcional)', { type: 'url', maxlength: 300, placeholder: 'https://servidor/organizacion/app.git' },
    'Público, por https://. Sin repositorio se deja una aplicación de ejemplo y subes tu código por SFTP a la carpeta «app».');
  const rama = campo('Rama', { type: 'text', maxlength: 100, placeholder: 'la principal del repositorio' });
  const entrada = campo('Entrada', { type: 'text', maxlength: 120 });
  const modo = lista('Modo', [{ valor: 'wsgi', texto: 'WSGI (Flask, Django)' }, { valor: 'asgi', texto: 'ASGI (FastAPI, Starlette)' }]);
  const carpeta = campo('Carpeta que se publica (del repositorio)', { type: 'text', maxlength: 120, placeholder: 'p. ej. dist' });
  const spa = casilla('Aplicación de una sola página (todas las rutas sirven index.html)', false);
  const ajustar = () => {
    const t = tipo.entrada.value;
    entrada.nodo.hidden = t === 'estatico';
    entrada.entrada.placeholder = t === 'python' ? 'app:app (módulo:objeto)' : 'server.js o «npm start»';
    modo.nodo.hidden = t !== 'python';
    carpeta.nodo.hidden = spa.nodo.hidden = t !== 'estatico';
  };
  tipo.entrada.addEventListener('change', ajustar);
  ajustar();
  const boton = el('button', { clase: 'boton', type: 'submit' }, 'Crear la aplicación');
  return el('form', { alSubmit: async (e) => {
    e.preventDefault();
    const t = tipo.entrada.value;
    const datos = { tipo: t, git: git.entrada.value.trim(), rama: rama.entrada.value.trim() };
    if (t !== 'estatico') datos.entrada = entrada.entrada.value.trim();
    if (t === 'python') datos.modo = modo.entrada.value;
    if (t === 'estatico') { datos.carpeta = carpeta.entrada.value.trim(); datos.spa = spa.entrada.checked; }
    const r = await hacer(msj, boton, 'Creando: descarga del código, dependencias (pip o npm) y arranque. Puede tardar varios minutos; no cierres esta página.',
      () => api.post(ruta, datos));
    if (r) alCrear();
  } }, el('div', { clase: 'rejilla' }, tipo.nodo, git.nodo, rama.nodo, entrada.nodo, modo.nodo, carpeta.nodo), spa.nodo,
  el('div', { clase: 'pie-form' }, boton));
}

function variables(ruta, e, msj, alGuardar) {
  const filas = el('div');
  const fila = (nombre) => {
    const n = el('input', { type: 'text', maxlength: 64, valor: nombre || '', 'aria-label': 'Nombre de la variable', placeholder: 'NOMBRE' });
    const v = el('input', { type: 'password', maxlength: 4096, 'aria-label': 'Valor', placeholder: nombre ? 'sin cambios' : 'valor', autocomplete: 'off' });
    const x = el('button', { clase: 'enlace peligro', type: 'button', alClick: () => f.remove() }, 'Quitar');
    const f = el('div', { clase: 'fila' }, el('div', { clase: 'crece' }, n), el('div', { clase: 'crece' }, v), x);
    f.leer = () => [n.value.trim().toUpperCase(), v.value === '' && nombre ? null : v.value];
    return f;
  };
  (e.variables || []).forEach(n => filas.append(fila(n)));
  const guardar = el('button', { clase: 'boton', type: 'button' }, 'Guardar y reiniciar');
  guardar.addEventListener('click', async () => {
    const datos = Object.fromEntries([...filas.children].map(f => f.leer()).filter(([n]) => n));
    if (await hacer(msj, guardar, 'Guardando y reiniciando la aplicación…', () => api.put(ruta + '/entorno', { variables: datos }))) alGuardar('Variables guardadas.');
  });
  return el('div', null, el('h2', null, 'Variables de entorno'),
    el('p', { clase: 'ayuda' }, 'Claves de API, la dirección de la base… Los valores no se vuelven a mostrar; vacío = conservar el guardado. PORT y HOST los pone el servidor.'),
    filas, el('div', { clase: 'fila' }, el('button', { clase: 'boton claro', type: 'button', alClick: () => filas.append(fila('')) }, 'Añadir variable'), guardar));
}

export async function pestanaPropia(ctx, mensaje) {
  const ruta = `/sitios/${enRutaSitio(ctx.sitio)}/propia`;
  const raiz = el('div');
  const msj = mensajes();
  const recargar = async (texto) => raiz.replaceWith(await pestanaPropia(ctx, texto));
  if (ctx.s.app && ctx.s.app !== 'propia') {
    return aviso('nota', `Este sitio ya tiene ${nombreApp(ctx.s.app)}. Las aplicaciones Node.js y Python van en un sitio vacío: crea un subdominio para ella.`);
  }
  if (ctx.s.app !== 'propia') {
    return agregar(raiz, el('h2', null, 'Aplicación Node.js, Python o estática'),
      el('p', { clase: 'ayuda' }, 'Corre con el usuario del sitio, con hasta 768 MB de memoria y 1,5 núcleos, detrás del cortafuegos de aplicación. Cuenta para el espacio en disco del dominio.'),
      msj.nodo, crear(ctx, ruta, msj, () => ctx.recargar()));
  }
  const e = await api.get(ruta);
  const [clase, texto] = ACTIVO[e.activo] || ['aviso-marca', e.activo || '—'];
  const boton = (que, etiqueta, espera) => {
    const b = el('button', { clase: que === 'desplegar' ? 'boton' : 'boton claro', type: 'button' }, etiqueta);
    b.addEventListener('click', async () => { if (await hacer(msj, b, espera, () => api.post(ruta + '/accion', { accion: que }))) recargar(`Hecho: ${etiqueta.toLowerCase()}.`); });
    return b;
  };
  const quitar = el('button', { clase: 'boton peligro', type: 'button' }, 'Quitar la aplicación');
  quitar.addEventListener('click', async () => {
    if (!await confirmar('Quitar la aplicación', 'Se detiene y su código va a la papelera del servidor. El sitio queda vacío.', 'Quitar', true)) return;
    if (await hacer(msj, quitar, 'Quitando…', () => api.del(`${ruta}?confirmacion=${encodeURIComponent(ctx.sitio)}`))) ctx.recargar();
  });
  const marcha = e.tipo === 'estatico' ? [] : [boton('reiniciar', 'Reiniciar', 'Reiniciando…'),
    e.activo === 'active' ? boton('detener', 'Detener', 'Deteniendo…') : boton('iniciar', 'Iniciar', 'Arrancando…')];
  return agregar(raiz,
    mensaje ? aviso('ok', mensaje) : null,
    el('div', { clase: 'fila' }, el('div', { clase: 'crece' }, el('h2', null, TIPOS.find(t => t.valor === e.tipo)?.texto || e.tipo),
      el('p', { clase: 'ayuda' }, [e.git ? `${e.git}${e.rama ? ' · ' + e.rama : ''}` : 'Código por SFTP en la carpeta «app»', e.entrada ? 'entrada ' + e.entrada : null].filter(Boolean).join(' · '))),
      el('span', { clase: 'marca ' + clase }, texto)),
    el('div', { clase: 'fila' }, e.git || e.tipo !== 'estatico' ? boton('desplegar', e.git ? 'Traer cambios y desplegar' : 'Instalar dependencias y reiniciar', 'Desplegando (puede tardar unos minutos)…') : null, ...marcha),
    msj.nodo,
    e.tipo === 'estatico' ? null : variables(ruta, e, msj, recargar),
    e.registros ? el('details', { clase: 'caja' }, el('summary', null, 'Registros de la aplicación'), el('pre', { clase: 'salida' }, e.registros)) : null,
    el('div', { clase: 'pie-form' }, quitar));
}
