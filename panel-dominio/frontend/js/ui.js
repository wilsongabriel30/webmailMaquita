// Construcción de la pantalla SIN innerHTML: todo texto entra como texto, nunca como HTML.
export function el(etiqueta, atributos, ...hijos) {
  const nodo = document.createElement(etiqueta);
  for (const [k, v] of Object.entries(atributos || {})) {
    if (v === null || v === undefined || v === false) continue;
    if (k === 'clase') nodo.className = v;
    else if (k.startsWith('al')) nodo.addEventListener(k.slice(2).toLowerCase(), v);
    else if (k === 'valor') nodo.value = v;
    else if (v === true) nodo.setAttribute(k, '');
    else nodo.setAttribute(k, v);
  }
  for (const h of hijos.flat()) {
    if (h === null || h === undefined || h === false) continue;
    nodo.append(h instanceof Node ? h : document.createTextNode(String(h)));
  }
  return nodo;
}

export const aviso = (tipo, texto) => el('p', { clase: 'aviso ' + tipo, role: tipo === 'error' ? 'alert' : 'status' }, texto);

export function campo(etiqueta, atributos, ayuda) {
  const entrada = el('input', atributos);
  return { nodo: el('div', null, el('label', null, etiqueta), entrada, ayuda ? el('p', { clase: 'ayuda' }, ayuda) : null), entrada };
}

export const GIB = 1024 ** 3;
export const enGB = (bytes) => (bytes > 0 ? (bytes / GIB).toLocaleString('es', { maximumFractionDigits: 1 }) + ' GB' : 'Sin límite');

/** Ventana con formulario. `alGuardar` devuelve una promesa; si falla, el error se muestra dentro. */
export function ventana(titulo, contenido, textoBoton, alGuardar, peligro) {
  const error = el('div');
  const guardar = el('button', { clase: 'boton' + (peligro ? ' peligro' : ''), type: 'submit' }, textoBoton);
  const cerrar = () => velo.remove();
  const formulario = el('form', { clase: 'caja', alSubmit: async (e) => {
    e.preventDefault();
    guardar.disabled = true;
    error.replaceChildren();
    try { await alGuardar(); cerrar(); } catch (err) { error.replaceChildren(aviso('error', err.message)); guardar.disabled = false; }
  } },
    el('h1', null, titulo), error, contenido,
    el('div', { clase: 'pie-form' }, el('button', { clase: 'boton claro', type: 'button', alClick: cerrar }, 'Cancelar'), guardar));
  const velo = el('div', { clase: 'velo', role: 'dialog', 'aria-modal': 'true' }, formulario);
  document.body.append(velo);
  const primero = formulario.querySelector('input, select');
  if (primero) primero.focus();
}

export function generarClave() {
  const letras = 'abcdefghijkmnpqrstuvwxyz', mayus = 'ABCDEFGHJKLMNPQRSTUVWXYZ', numeros = '23456789', simbolos = '.-_+*';
  const todo = letras + mayus + numeros + simbolos;
  const azar = (n) => crypto.getRandomValues(new Uint32Array(1))[0] % n;
  const c = [letras, mayus, numeros, simbolos].map(s => s[azar(s.length)]);
  while (c.length < 16) c.push(todo[azar(todo.length)]);
  for (let i = c.length - 1; i > 0; i--) { const j = azar(i + 1); [c[i], c[j]] = [c[j], c[i]]; }
  return c.join('');
}
