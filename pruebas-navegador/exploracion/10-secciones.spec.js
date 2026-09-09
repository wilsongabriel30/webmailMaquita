// Recorre TODAS las secciones como una persona que abre el menú y entra en cada una.
//
// Qué se comprueba en cada sección: que carga sin excepciones, que pinta algo de verdad (no una
// pantalla en blanco), que no manda a la pantalla de entrada teniendo sesión, y qué peticiones
// fallan por detrás mientras «parece» que funciona.
const { test, expect } = require('../pruebas/base');
const { apartarAvisos } = require('../pruebas/apoyo');
const { SECCIONES, SECCIONES_ADMIN } = require('./mapa');
const { observar, hayAlgo } = require('./observador');
const { anotar, volcar } = require('./informe');

test.describe.configure({ mode: 'serial' });

test('cada sección abre y se sostiene', async ({ sesion }) => {
  test.setTimeout(300_000);
  const { pagina } = sesion;
  const ojo = observar(pagina);

  for (const seccion of SECCIONES) {
    await pagina.goto(seccion.ruta, { waitUntil: 'domcontentloaded' }).catch(() => {});
    await pagina.waitForTimeout(2500);
    await apartarAvisos(pagina);

    // 1. No puede mandarnos a la entrada teniendo sesión.
    if (/\/login/.test(pagina.url())) {
      anotar('alta', seccion.nombre, 'manda a la pantalla de entrada teniendo sesión válida', seccion.ruta);
      continue;
    }

    // 2. No puede quedarse en blanco: una persona ve una pantalla vacía y da por roto el producto.
    const texto = (await pagina.locator('body').innerText().catch(() => '')).trim();
    if (texto.length < 40) {
      anotar('alta', seccion.nombre, 'la pantalla queda prácticamente vacía', `${texto.length} caracteres visibles`);
    }

    // 3. Nada de pantallas de error del propio armazón.
    for (const senal of [/algo salió mal|algo salio mal/i, /error inesperado/i, /failed to fetch/i,
                         /cannot read (properties|property)/i, /undefined is not/i]) {
      if (senal.test(texto)) anotar('alta', seccion.nombre, 'muestra un error a la persona', String(senal));
    }

    // 4. Lo que pasó por detrás.
    const visto = ojo.cosecha();
    if (hayAlgo(visto)) {
      for (const e of visto.excepciones) anotar('alta', seccion.nombre, 'excepción en la página', e);
      for (const f of visto.fallidas) {
        const grave = /^5\d\d/.test(f);
        anotar(grave ? 'alta' : 'media', seccion.nombre, 'petición fallida', f);
      }
      for (const c of visto.consola) anotar('media', seccion.nombre, 'error en la consola', c);
    }

    // 5. Cuántas cosas se pueden pulsar aquí: si son cero, la sección no ofrece nada.
    const pulsables = await pagina.locator('button:visible, [role="button"]:visible, a[href]:visible').count();
    if (pulsables === 0) anotar('alta', seccion.nombre, 'no hay nada que se pueda pulsar', seccion.ruta);
    console.log(`   · ${seccion.nombre}: ${pulsables} elementos a la vista`);
  }

  // Administración con una cuenta que no administra: tiene que negarse con cabeza, no reventar.
  for (const seccion of SECCIONES_ADMIN) {
    await pagina.goto(seccion.ruta, { waitUntil: 'domcontentloaded' }).catch(() => {});
    await pagina.waitForTimeout(2000);
    const texto = (await pagina.locator('body').innerText().catch(() => '')).trim();
    const visto = ojo.cosecha();
    for (const e of visto.excepciones) anotar('alta', seccion.nombre, 'excepción al rechazar el acceso', e);
    if (texto.length < 40) {
      anotar('media', seccion.nombre, 'al negar el acceso deja la pantalla vacía, sin explicar nada', seccion.ruta);
    }
  }

  volcar();
  expect(true).toBe(true); // Esta prueba informa; las conclusiones salen del informe.
});
