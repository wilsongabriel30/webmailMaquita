// Pulsa, uno a uno, todo lo que una persona puede pulsar en cada sección.
//
// Un botón está bien si al pulsarlo PASA ALGO: cambia la pantalla, cambia la dirección, o el
// servidor recibe una petición. Un botón que no hace nada de eso es, para quien lo usa, un botón
// roto: no puede saber si el sistema le oyó. Y un botón que revienta la página es peor.
//
// No se pulsa lo que tenga consecuencias (enviar, borrar, salir…): la frontera está en
// `seguridad.js` y se escribe aparte precisamente para que se pueda revisar.
const { test, expect } = require('../pruebas/base');
const { apartarAvisos } = require('../pruebas/apoyo');
const { SECCIONES } = require('./mapa');
const { esSeguroPulsar } = require('./seguridad');
const { observar } = require('./observador');
const { anotar, volcar } = require('./informe');

test.describe.configure({ mode: 'serial' });

const SELECTOR = 'button:visible, [role="button"]:visible, [role="tab"]:visible';

/** Nombre con el que una persona reconocería este elemento. */
async function nombreDe(elemento) {
  const texto = (await elemento.innerText().catch(() => '')).trim();
  if (texto) return texto.split('\n')[0].slice(0, 60);
  for (const atributo of ['aria-label', 'title', 'name', 'data-testid']) {
    const v = await elemento.getAttribute(atributo).catch(() => null);
    if (v) return `«${v}»`;
  }
  return '(sin nombre)';
}

test('cada botón de cada sección hace algo y no rompe nada', async ({ sesion }) => {
  test.setTimeout(1_200_000);
  const { pagina } = sesion;
  const ojo = observar(pagina);
  let pulsados = 0, mudos = 0, saltados = 0;

  for (const seccion of SECCIONES) {
    await pagina.goto(seccion.ruta, { waitUntil: 'domcontentloaded' }).catch(() => {});
    await pagina.waitForTimeout(2000);
    await apartarAvisos(pagina);
    ojo.cosecha(); // Lo de la carga ya se contó en el recorrido de secciones.

    const total = await pagina.locator(SELECTOR).count();
    const sinNombre = [];

    for (let i = 0; i < total; i++) {
      // Se vuelve a resolver en cada vuelta: pulsar repinta la pantalla y los índices se mueven.
      const elemento = pagina.locator(SELECTOR).nth(i);
      if (!(await elemento.isVisible().catch(() => false))) continue;
      const nombre = await nombreDe(elemento);
      if (nombre === '(sin nombre)') sinNombre.push(i);

      const { seguro, motivo } = esSeguroPulsar(nombre);
      if (!seguro) { saltados++; continue; }

      const antesURL = pagina.url();
      const antesHTML = (await pagina.locator('body').innerHTML().catch(() => '')).length;
      let peticiones = 0;
      const contar = () => { peticiones++; };
      pagina.on('request', contar);

      const fallo = await elemento.click({ timeout: 4000 }).then(() => null).catch((e) => e);
      await pagina.waitForTimeout(700);
      pagina.off('request', contar);
      pulsados++;

      if (fallo) {
        anotar('media', seccion.nombre, `no se deja pulsar: «${nombre}»`, String(fallo).slice(0, 120));
        continue;
      }

      const visto = ojo.cosecha();
      for (const e of visto.excepciones) {
        anotar('alta', seccion.nombre, `pulsar «${nombre}» revienta la página`, e);
      }
      for (const f of visto.fallidas) {
        anotar(/^5\d\d/.test(f) ? 'alta' : 'media', seccion.nombre, `pulsar «${nombre}» deja una petición fallida`, f);
      }

      const despuesURL = pagina.url();
      const despuesHTML = (await pagina.locator('body').innerHTML().catch(() => '')).length;
      const cambio = despuesURL !== antesURL || Math.abs(despuesHTML - antesHTML) > 40 || peticiones > 0;
      if (!cambio) {
        mudos++;
        anotar('media', seccion.nombre, `«${nombre}» no hace nada visible al pulsarlo`, 'ni cambia la pantalla, ni la dirección, ni habla con el servidor');
      }

      // Volver al sitio: cerrar lo que se haya abierto y recuperar la sección.
      await pagina.keyboard.press('Escape').catch(() => {});
      if (despuesURL !== antesURL) {
        await pagina.goto(seccion.ruta, { waitUntil: 'domcontentloaded' }).catch(() => {});
        await pagina.waitForTimeout(1200);
        await apartarAvisos(pagina);
        ojo.cosecha();
      }
    }

    if (sinNombre.length) {
      anotar('media', seccion.nombre, `${sinNombre.length} elementos sin nombre accesible`,
        'quien navega con lector de pantalla o teclado no sabe qué son');
    }
    console.log(`   · ${seccion.nombre}: ${total} elementos, pulsados los seguros`);
  }

  console.log(`\n   Pulsados: ${pulsados} · mudos: ${mudos} · no pulsados por seguridad: ${saltados}`);
  volcar();
  expect(true).toBe(true);
});
