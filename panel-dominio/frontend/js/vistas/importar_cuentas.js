// Importar cuentas desde un CSV: vista previa fila a fila y después crear las válidas.
// Se descarga solo al abrirla. El portal no admite peticiones de más de 64 KB, así que el archivo
// se manda por bloques de filas (cada uno con la cabecera); el servidor revisa cada bloque entero.
import { api } from '../api.js';
import { el, agregar, aviso } from '../ui.js';

const BLOQUE = 40 * 1024;
const MAX_BYTES = 1024 * 1024;
const MAX_FILAS = 2000;
const PLANTILLA = 'correo,nombre,clave,cuota_mb,alias\r\nana.perez@example.org,Ana Pérez,,1024,ventas@example.org;info@example.org\r\n';
// Lo que ocupa el texto ya dentro del JSON de la petición (comillas y saltos escapados).
const bytes = (t) => new TextEncoder().encode(JSON.stringify(t)).length - 2;

async function leerTexto(archivo) {
  const datos = await archivo.arrayBuffer();
  try { return new TextDecoder('utf-8', { fatal: true }).decode(datos); } catch { return new TextDecoder('windows-1252').decode(datos); }
}

function descargar(nombre, contenido) {
  const url = URL.createObjectURL(new Blob(['﻿' + contenido], { type: 'text/csv;charset=utf-8' }));
  const a = el('a', { href: url, download: nombre });
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/** Registros del CSV respetando comillas (un campo entre comillas puede llevar saltos de línea). */
function registros(texto) {
  texto = texto.replace(/^﻿/, '');
  const lista = [];
  let inicio = 0, comillas = false, linea = 1, lineaInicio = 1;
  for (let i = 0; i < texto.length; i++) {
    if (texto[i] === '"') comillas = !comillas;
    else if (texto[i] === '\n') {
      linea++;
      if (!comillas) { lista.push({ texto: texto.slice(inicio, i + 1), linea: lineaInicio }); inicio = i + 1; lineaInicio = linea; }
    }
  }
  if (inicio < texto.length) lista.push({ texto: texto.slice(inicio) + '\n', linea: lineaInicio });
  return lista;
}

/** Bloques de hasta BLOQUE bytes: la cabecera más filas seguidas, y desde qué línea del archivo empiezan. */
export function bloques(texto) {
  const todos = registros(texto);
  if (!todos.length) throw new Error('El archivo está vacío');
  const [cabecera, ...filas] = todos;
  const conDatos = filas.filter(r => r.texto.trim().replace(/[,;]/g, ''));
  if (conDatos.length > MAX_FILAS) throw new Error(`El archivo tiene más de ${MAX_FILAS} filas: divídelo en varios`);
  const lista = [];
  let actual = null;
  for (const r of filas) {
    const tam = bytes(r.texto);
    if (bytes(cabecera.texto) + tam > BLOQUE) throw new Error(`La fila de la línea ${r.linea} es demasiado larga`);
    if (!actual || actual.tam + tam > BLOQUE) {
      actual = { csv: cabecera.texto, tam: bytes(cabecera.texto), desplazamiento: r.linea - 2 };
      lista.push(actual);
    }
    actual.csv += r.texto;
    actual.tam += tam;
  }
  if (!lista.length) throw new Error('El archivo no tiene filas debajo de la cabecera');
  return lista;
}

const sumar = (a, b) => { for (const [k, n] of Object.entries(b || {})) a[k] = (a[k] || 0) + n; };

/** Marca lo que se repite entre bloques (dentro de cada uno ya lo hace el servidor). */
function repetidosEntreBloques(filas, vistas) {
  for (const f of filas) {
    for (const d of [f.correo, ...f.alias]) {
      if (d && vistas.has(d) && vistas.get(d) !== f.fila) { f.errores.push(`${d} ya aparece en la fila ${vistas.get(d)}`); f.valida = false; }
    }
    for (const d of [f.correo, ...f.alias]) if (d && !vistas.has(d)) vistas.set(d, f.fila);
  }
}

function tabla(filas, soloErrores) {
  const visibles = soloErrores ? filas.filter(f => f.errores.length) : filas;
  return el('div', { clase: 'caja tabla-marco' }, el('table', null,
    el('thead', null, el('tr', null, ['Fila', 'Cuenta', 'Cuota', 'Alias', 'Contraseña', 'Estado'].map(t => el('th', null, t)))),
    el('tbody', null, visibles.length ? visibles.map(f => el('tr', null,
      el('td', null, String(f.fila)),
      el('td', null, el('strong', null, f.correo || '—'), el('div', { clase: 'ayuda' }, f.nombre)),
      el('td', null, f.cuota_mb ? `${f.cuota_mb} MB` : '—'),
      el('td', null, f.alias.join(', ')),
      el('td', null, f.clave),
      el('td', null, f.errores.length ? el('span', { clase: 'marca no' }, f.errores.join('. '))
        : el('span', { clase: 'marca si' }, f.resultado === 'creada' ? 'Creada' : 'Lista'))))
      : [el('tr', null, el('td', { colspan: '6', clase: 'vacio' }, 'No hay filas con errores.'))])));
}

export async function vistaImportar(sesion, alVolver) {
  const raiz = el('div');
  const estado = el('div');
  const resultados = el('div');
  let partes = null, filas = [];

  const solo = el('input', { type: 'checkbox', id: 'imp-solo', alChange: () => pintarFilas() });
  const pintarFilas = () => resultados.replaceChildren(filas.length
    ? el('div', null, el('p', { clase: 'casilla' }, solo, ' ', el('label', { for: 'imp-solo', clase: 'en-linea' }, 'Ver solo las filas con errores')), tabla(filas, solo.checked))
    : '');

  const revisar = el('button', { clase: 'boton claro', disabled: true, alClick: async () => {
    revisar.disabled = true; crear.hidden = true; estado.replaceChildren(aviso('ok', 'Revisando…'));
    try {
      const pendientes = { cuentas: {}, alias: {} };
      const vistas = new Map();
      filas = [];
      for (const b of partes) {
        const r = await api.post('/importar-cuentas/vista-previa', { csv: b.csv, desplazamiento: b.desplazamiento, pendientes });
        repetidosEntreBloques(r.filas, vistas);
        filas.push(...r.filas);
        sumar(pendientes.cuentas, r.ocupa.cuentas);
        sumar(pendientes.alias, r.ocupa.alias);
      }
      const validas = filas.filter(f => f.valida).length;
      estado.replaceChildren(aviso(filas.length - validas ? 'error' : 'ok',
        `${validas} fila(s) listas y ${filas.length - validas} con errores (se omitirán). Aún no se ha creado nada.`));
      crear.textContent = `Crear ${validas} cuenta(s)`;
      crear.hidden = !validas;
    } catch (err) { estado.replaceChildren(aviso('error', err.message)); filas = []; }
    revisar.disabled = false;
    pintarFilas();
  } }, 'Revisar archivo');

  const crear = el('button', { clase: 'boton', hidden: true, alClick: async () => {
    if (!confirm('Se crearán las filas válidas; las que tienen errores se omiten. ¿Continuar?')) return;
    crear.disabled = revisar.disabled = true;
    estado.replaceChildren(aviso('ok', 'Creando cuentas…'));
    let creadas = 0, informe = '', claves = '';
    filas = [];
    estado.replaceChildren();
    try {
      for (const b of partes) {
        const r = await api.post('/importar-cuentas/aplicar', { csv: b.csv, desplazamiento: b.desplazamiento });
        creadas += r.creadas;
        filas.push(...r.resultados);
        informe += informe ? r.informe_csv.split('\r\n').slice(1).join('\r\n') : r.informe_csv;
        if (r.claves_csv) claves += claves ? r.claves_csv.split('\r\n').slice(1).join('\r\n') : r.claves_csv;
      }
    } catch (err) {
      estado.append(aviso('error', `${err.message} (se crearon ${creadas} cuentas antes del error; revisa el informe).`));
    }
    crear.hidden = true;
    agregar(estado,
      aviso('ok', `Se crearon ${creadas} cuenta(s); se omitieron ${filas.length - creadas}.`),
      el('div', { clase: 'fila' },
        el('button', { clase: 'boton claro', alClick: () => descargar('informe-importacion.csv', informe) }, 'Descargar informe'),
        claves ? el('button', { clase: 'boton', alClick: () => descargar('contrasenas-generadas.csv', claves) }, 'Descargar contraseñas generadas') : null),
      claves ? aviso('error', 'Las contraseñas generadas solo se muestran ahora: descárgalas antes de salir y entrégalas por un medio seguro.') : null);
    pintarFilas();
  } }, 'Crear cuentas');

  const archivo = el('input', { type: 'file', accept: '.csv,text/csv', 'aria-label': 'Archivo CSV', alChange: async (e) => {
    partes = null; filas = []; crear.hidden = true; revisar.disabled = true; pintarFilas();
    const f = e.target.files[0];
    if (!f) return;
    if (f.size > MAX_BYTES) { estado.replaceChildren(aviso('error', 'El archivo pesa más de 1 MB: divídelo en varios.')); return; }
    try {
      partes = bloques(await leerTexto(f));
      estado.replaceChildren(aviso('ok', `${f.name}: listo para revisar.`));
      revisar.disabled = false;
    } catch (err) { estado.replaceChildren(aviso('error', err.message)); }
  } });

  agregar(raiz,
    el('h1', null, 'Importar cuentas desde un archivo CSV'),
    el('p', { clase: 'sub' }, sesion.dominios.join(', ')),
    el('p', { clase: 'ayuda' }, 'Columnas: correo y nombre (obligatorias), clave (si falta, se genera una), cuota_mb (si falta, la del dominio) y alias (separados por punto y coma). Hasta 2000 filas. Primero se revisa todo sin crear nada; las cuentas se crean dentro de los límites de tu dominio.'),
    el('div', { clase: 'fila' }, archivo, revisar, crear,
      el('button', { clase: 'enlace', alClick: () => descargar('plantilla-cuentas.csv', PLANTILLA) }, 'Descargar plantilla'),
      el('button', { clase: 'enlace', alClick: () => alVolver(raiz) }, 'Volver a las cuentas')),
    estado, resultados);
  return raiz;
}
