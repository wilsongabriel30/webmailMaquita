// Segunda pasada: cada sospechoso de la primera, mirado de cerca.
//
// Una exploración automática señala más de lo que hay: el elemento del menú de la sección en la
// que YA estás no hace nada porque no tiene que hacer nada, y un botón que exige selección
// previa se niega con razón. Sin esta pasada, la lista de arreglos mezcla fallos con normalidad,
// y una lista así no se puede trabajar.
//
// De cada sospechoso se dice: si está deshabilitado (y si eso se VE), si algo lo tapa, y qué
// ocurre al forzar la pulsación.
const fs = require('fs');
const path = require('path');
const { test, expect } = require('../pruebas/base');
const { apartarAvisos } = require('../pruebas/apoyo');
const { SECCIONES } = require('./mapa');

const ENTRADA = process.env.SOSPECHOSOS
  || path.join(__dirname, '..', 'informe-secciones-botones.json');
const SALIDA = process.env.VEREDICTOS
  || path.join(__dirname, '..', 'veredictos.json');

/** Los hallazgos que hay que mirar de cerca, con el nombre del botón ya extraído. */
function sospechosos() {
  const { hallazgos } = JSON.parse(fs.readFileSync(ENTRADA, 'utf8'));
  const lista = [];
  for (const h of hallazgos) {
    const mudo = /«(.+)» no hace nada visible/.exec(h.que);
    const duro = /no se deja pulsar: «(.+)»/.exec(h.que);
    const nombre = (mudo || duro) ? (mudo || duro)[1].replace(/^«|»$/g, '') : null;
    if (!nombre) continue;
    const seccion = SECCIONES.find((s) => s.nombre === h.seccion);
    if (!seccion) continue;
    lista.push({ seccion, nombre, tipo: mudo ? 'mudo' : 'no se deja pulsar' });
  }
  return lista;
}

test('cada sospechoso, mirado de cerca', async ({ sesion }) => {
  test.setTimeout(900_000);
  const { pagina } = sesion;
  const veredictos = [];

  for (const caso of sospechosos()) {
    await pagina.goto(caso.seccion.ruta, { waitUntil: 'domcontentloaded' }).catch(() => {});
    await pagina.waitForTimeout(1500);
    await apartarAvisos(pagina);

    const elemento = pagina.getByRole('button', { name: caso.nombre, exact: false }).first();
    const hay = await elemento.count().catch(() => 0);
    if (!hay) {
      veredictos.push({ ...caso, seccion: caso.seccion.nombre, veredicto: 'no se encuentra en una carga limpia',
        nota: 'aparecía en otro estado de la pantalla' });
      continue;
    }

    const estado = await elemento.evaluate((el) => {
      const s = getComputedStyle(el);
      const r = el.getBoundingClientRect();
      const centro = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
      return {
        deshabilitado: el.disabled === true || el.getAttribute('aria-disabled') === 'true',
        seVeDeshabilitado: parseFloat(s.opacity) < 0.7 || s.cursor === 'not-allowed',
        punteroInerte: s.pointerEvents === 'none',
        tapadoPor: centro && !el.contains(centro) ? (centro.tagName + '.' + String(centro.className).slice(0, 40)) : null,
        esMenuDeLaSeccionActual: el.getAttribute('aria-current') === 'page' || /activ|selected|current/i.test(String(el.className)),
        etiqueta: el.tagName,
      };
    }).catch(() => null);

    // Forzar la pulsación: si con `force` sí pasa algo, el problema es que algo lo tapa.
    const antes = (await pagina.locator('body').innerHTML().catch(() => '')).length;
    await elemento.click({ force: true, timeout: 3000 }).catch(() => {});
    await pagina.waitForTimeout(900);
    const despues = (await pagina.locator('body').innerHTML().catch(() => '')).length;
    const cambiaForzado = Math.abs(despues - antes) > 40;

    let veredicto;
    if (estado?.esMenuDeLaSeccionActual) veredicto = 'normal: es la sección en la que ya estamos';
    else if (estado?.deshabilitado && estado.seVeDeshabilitado) veredicto = 'normal: deshabilitado y se nota';
    else if (estado?.deshabilitado) veredicto = 'A REVISAR: deshabilitado pero no se nota (parece pulsable)';
    else if (estado?.tapadoPor) veredicto = `A REVISAR: algo lo tapa (${estado.tapadoPor})`;
    else if (estado?.punteroInerte) veredicto = 'A REVISAR: no recibe pulsaciones (pointer-events: none)';
    else if (cambiaForzado) veredicto = 'A REVISAR: forzando la pulsación sí responde';
    else veredicto = 'A REVISAR: pulsable, sin respuesta';

    veredictos.push({ seccion: caso.seccion.nombre, nombre: caso.nombre, tipo: caso.tipo, veredicto, estado });
    console.log(`   · [${caso.seccion.nombre}] ${caso.nombre}: ${veredicto}`);
    await pagina.keyboard.press('Escape').catch(() => {});
  }

  fs.writeFileSync(SALIDA, JSON.stringify({ generado: new Date().toISOString(), veredictos }, null, 2));
  console.log(`\n   Veredictos: ${veredictos.length} en ${SALIDA}`);
  expect(true).toBe(true);
});
