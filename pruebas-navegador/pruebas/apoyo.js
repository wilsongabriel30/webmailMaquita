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

// Ruido conocido de una instalación con el chat en OTRA máquina (aviso de Andes, 09/09/2026).
//
// Dos peticiones fallan por diseño y no son fallos del producto. Antes se apartaba «todo lo del
// chat», y esa venda escondía los 404 de verdad; después se apartó solo el 401 con `/api/chat`
// en la ruta, y entonces estos dos hacían fallar dos de tres recorridos. Aquí se apartan estos
// casos y NADA más: cada uno con su ruta exacta y, cuando corresponde, un tope de veces.
const RUIDO_CONOCIDO = [
  {
    patron: /^404 GET .*\/api\/chat\/conversations$/,
    veces: 1, // Carrera única al arrancar: la segunda ya no es «la carrera», es un fallo.
    porque: 'la carrera de arranque del contador de no leídos (una sola vez)',
  },
  {
    patron: /^401 \w+ .*\/sso\/entrar$/,
    porque: 'la cuenta de pruebas no está en el directorio del chat',
  },
  {
    patron: /^401 \w+ .*\/api\/chat/,
    porque: 'sesión de chat ausente para una cuenta fuera de su directorio',
  },
];

/** Separa las peticiones fallidas en ruido conocido y fallos de verdad.
 *  Devuelve `{ reales, ruido }`. Lo apartado se muestra: un filtro callado es una venda. */
function separarRuido(fallidas) {
  const reales = [];
  const ruido = [];
  const vistas = new Map();
  for (const f of fallidas) {
    const regla = RUIDO_CONOCIDO.find((r) => r.patron.test(f));
    if (!regla) {
      reales.push(f);
      continue;
    }
    const cuenta = (vistas.get(regla) || 0) + 1;
    vistas.set(regla, cuenta);
    // Con tope: lo que pase de la cuenta prevista deja de ser ruido y vuelve a ser un fallo.
    if (regla.veces && cuenta > regla.veces) reales.push(f);
    else ruido.push(`${f}  (${regla.porque})`);
  }
  return { reales, ruido };
}

/** Comprueba que no quedan peticiones fallidas, apartando solo el ruido conocido y diciéndolo. */
function sinPeticionesFallidas(fallidas, contexto) {
  const { reales, ruido } = separarRuido(fallidas);
  for (const r of ruido) console.log('   ruido conocido:', r);
  expect(reales, contexto).toEqual([]);
}

// Con certificado propio, `ignoreHTTPSErrors` no alcanza al *service worker*: su fetch nace
// fuera del contexto y tumbaba el recorrido de entrada. Bajo TLS laxo se bloquea el worker.
const TLS_LAXA = process.env.PRUEBAS_TLS_LAXA === '1';
const OPCIONES_CONTEXTO = {
  locale: 'es-EC',
  ignoreHTTPSErrors: TLS_LAXA,
  serviceWorkers: TLS_LAXA ? 'block' : 'allow',
};

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

module.exports = {
  USUARIO, CLAVE, vigilar, entrar, apartarAvisos, abrirCorreo,
  separarRuido, sinPeticionesFallidas, TLS_LAXA, OPCIONES_CONTEXTO,
};
