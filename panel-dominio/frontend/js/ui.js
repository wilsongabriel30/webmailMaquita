// Construcción de la pantalla SIN innerHTML: todo texto entra como texto, nunca como HTML.
export function el(etiqueta, atributos, ...hijos) {
  const nodo = document.createElement(etiqueta);
  for (const [k, v] of Object.entries(atributos || {})) {
    if (v === null || v === undefined || v === false) continue;
    if (k === 'clase') nodo.className = v;
    // Eventos: alClick, alSubmit… (al + mayúscula). «alt» y compañía son atributos normales.
    else if (/^al[A-Z]/.test(k)) nodo.addEventListener(k.slice(2).toLowerCase(), v);
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

/** Agrega hijos a un nodo que ya existe, con las mismas reglas que el(): sin huecos y todo como texto. */
export function agregar(nodo, ...hijos) {
  for (const h of hijos.flat()) {
    if (h === null || h === undefined || h === false) continue;
    nodo.append(h instanceof Node ? h : document.createTextNode(String(h)));
  }
  return nodo;
}

export const aviso = (tipo, texto) => el('p', { clase: 'aviso ' + tipo, role: tipo === 'error' ? 'alert' : 'status' }, texto);

// Cada etiqueta va enlazada a su casilla (for/id): así la lee un lector de pantalla y
// tocar la etiqueta lleva el cursor al campo.
let siguienteId = 0;
const idNuevo = () => 'c' + (++siguienteId);

export function campo(etiqueta, atributos, ayuda) {
  const id = idNuevo();
  const pista = ayuda ? el('p', { clase: 'ayuda', id: id + '-ayuda' }, ayuda) : null;
  const entrada = el('input', { ...atributos, id, 'aria-describedby': ayuda ? id + '-ayuda' : null });
  return { nodo: el('div', null, el('label', { for: id }, etiqueta), entrada, pista), entrada };
}

export function casilla(etiqueta, marcada) {
  const id = idNuevo();
  const entrada = el('input', { type: 'checkbox', id });
  entrada.checked = !!marcada;
  return { nodo: el('p', { clase: 'casilla' }, entrada, ' ', el('label', { for: id, clase: 'en-linea' }, etiqueta)), entrada };
}

export function lista(etiqueta, opciones) {
  const id = idNuevo();
  const entrada = el('select', { id }, opciones.map(o => el('option', { value: o.valor }, o.texto)));
  return { nodo: el('div', null, el('label', { for: id }, etiqueta), entrada), entrada };
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
  const velo = el('div', { clase: 'velo', role: 'dialog', 'aria-modal': 'true', 'aria-label': titulo, alKeydown: (e) => { if (e.key === 'Escape') cerrar(); } }, formulario);
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
