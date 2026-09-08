// Piezas comunes: entrar al webmail como una persona y vigilar lo que la página hace por detrás.
//
// Regla de estas pruebas: nunca dar por buena una entrada que no ocurrió. La primera versión
// esperaba una URL que ya coincidía con la pantalla de entrada, así que una prueba pasaba sin
// haber iniciado sesión. Aquí se comprueba la respuesta del servidor y que la pantalla cambió.
const { expect } = require('@playwright/test');

const USUARIO = process.env.PRUEBAS_USUARIO || '';
const CLAVE = process.env.PRUEBAS_CLAVE || '';

/** Recoge errores de consola y peticiones fallidas mientras dura la prueba. */
function vigilar(page) {
  const consola = [];
  const fallidas = [];
  page.on('console', (m) => {
    if (m.type() === 'error') consola.push(m.text().slice(0, 200));
  });
  page.on('response', (r) => {
    if (r.status() >= 400) fallidas.push(`${r.status()} ${r.request().method()} ${new URL(r.url()).pathname}`);
  });
  page.on('pageerror', (e) => consola.push('excepción: ' + String(e).slice(0, 200)));
  return { consola, fallidas };
}

/** Entra al webmail rellenando el formulario, como una persona. Falla si no entra de verdad. */
async function entrar(page) {
  expect(USUARIO, 'falta la variable PRUEBAS_USUARIO').not.toBe('');
  expect(CLAVE, 'falta la variable PRUEBAS_CLAVE').not.toBe('');

  await page.goto('/webmail/login', { waitUntil: 'domcontentloaded' });
  await page.locator('input[type="email"], input[type="text"]').first().fill(USUARIO);
  await page.locator('input[type="password"]').first().fill(CLAVE);

  const respuesta = page.waitForResponse(
    (r) => /\/api\/auth\/(login|token|iniciar)/.test(r.url()) && r.request().method() === 'POST',
    { timeout: 30_000 },
  );
  await page.getByRole('button', { name: /iniciar sesión|entrar|acceder/i }).first().click();
  const r = await respuesta;
  expect(r.status(), `el servidor rechazó la entrada de ${USUARIO}`).toBeLessThan(400);

  // La pantalla tiene que cambiar de verdad: sin esto, una prueba puede pasar sin sesión.
  await expect(page).not.toHaveURL(/\/login/, { timeout: 30_000 });
  await expect(page.locator('input[type="password"]')).toHaveCount(0, { timeout: 20_000 });
}

/** Quita de en medio los avisos que tapan la interfaz (campaña de verificación en dos pasos).
 *  Una persona los cierra sin pensar; la prueba tiene que hacer lo mismo o no ve nada debajo. */
async function apartarAvisos(page) {
  for (const texto of [/más tarde|mas tarde/i, /ya la activé|ya la active/i, /cerrar/i]) {
    const boton = page.getByRole('button', { name: texto }).first();
    if (await boton.count() && await boton.isVisible().catch(() => false)) {
      await boton.click().catch(() => {});
      await page.waitForTimeout(300);
      return true;
    }
  }
  return false;
}

/** Abre el correo con la sesión ya guardada y deja la pantalla lista para trabajar. */
async function abrirCorreo(page, opciones = {}) {
  await page.goto('/webmail/', { waitUntil: opciones.espera || 'networkidle' });
  await apartarAvisos(page);
  return page;
}

module.exports = { USUARIO, CLAVE, vigilar, entrar, apartarAvisos, abrirCorreo };
