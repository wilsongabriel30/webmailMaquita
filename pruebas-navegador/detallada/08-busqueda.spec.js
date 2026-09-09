// La búsqueda, usada como la usa una persona: con el ratón, desde el panel.
//
// El rango de fechas ya falló una vez de una forma que no se ve en el código: nginx bloquea
// cualquier «..» en la URL (defensa contra path traversal) y la consulta devolvía 403 sin llegar
// al correo. Por eso esta prueba mira lo que ve quien busca —si aparecen resultados o un error—
// y además cuánto tarda.
const fs = require('fs');
const path = require('path');
const { test, expect } = require('../pruebas/base');
const { abrirCorreo } = require('../pruebas/apoyo');

const CAPTURAS = path.join(__dirname, '..', 'capturas', 'busqueda');
fs.mkdirSync(CAPTURAS, { recursive: true });

/** Espera a que la lista deje de cargar y devuelve lo que se ve. */
async function esperarResultados(pagina) {
  const t0 = Date.now();
  await pagina.waitForTimeout(600);
  // La cabecera de la lista dice «Buscando «...»» mientras hay búsqueda activa.
  await pagina.waitForFunction(() => {
    const cuerpo = document.body.innerText || '';
    return !/cargando|buscando\.\.\./i.test(cuerpo);
  }, { timeout: 120_000 }).catch(() => {});
  const ms = Date.now() - t0;
  const texto = await pagina.locator('body').innerText();
  const filas = await pagina.locator('[data-uid], [class*="message-row"]').count();
  const hayError = /error|no se pudo|403|problema/i.test(texto);
  return { ms, filas, hayError };
}

test.describe.configure({ mode: 'serial' });

test('el panel de búsqueda avanzada busca por rango de fechas', async ({ sesion }) => {
  test.setTimeout(300_000);
  const { pagina } = sesion;
  await abrirCorreo(pagina);

  // El botón del embudo, junto a la caja de búsqueda.
  const abrir = pagina.getByRole('button', { name: /búsqueda avanzada/i }).first();
  await expect(abrir, 'debería existir el botón de búsqueda avanzada').toBeVisible({ timeout: 20_000 });
  await abrir.click();
  await pagina.waitForTimeout(700);
  await pagina.screenshot({ path: path.join(CAPTURAS, '1-panel-abierto.png') });

  // Un rango de fechas, como lo pondría una persona: con los dos calendarios. Se elige un rango
  // que INCLUYA HOY: con uno de meses atrás la cuenta de pruebas no tiene nada, y un «sin
  // resultados» limpio no demuestra que el rango funcione, solo que no da error.
  const hoy = new Date();
  const ayer = new Date(hoy.getTime() - 24 * 3600 * 1000);
  const manana = new Date(hoy.getTime() + 24 * 3600 * 1000);
  const iso = (d) => d.toISOString().slice(0, 10);
  await pagina.getByLabel('Desde').fill(iso(ayer));
  await pagina.getByLabel('Hasta').fill(iso(manana));
  await pagina.waitForTimeout(300);
  await pagina.screenshot({ path: path.join(CAPTURAS, '2-rango-puesto.png') });

  // Lo que el panel va a enviar, a la vista.
  const consulta = await pagina.locator('div[class*="font-mono"]').first().innerText().catch(() => '');
  console.log(`   consulta compuesta:  ${consulta}`);

  await pagina.getByRole('button', { name: /^Buscar$/ }).first().click();
  const r = await esperarResultados(pagina);
  await pagina.screenshot({ path: path.join(CAPTURAS, '3-resultados-rango.png') });

  console.log(`   rango de fechas:     ${r.ms} ms, ${r.filas} filas, ¿error? ${r.hayError ? 'SÍ' : 'no'}`);
  expect(r.hayError, 'la búsqueda por rango no debería dar error').toBe(false);
  // Y tiene que DEVOLVER algo: el buzón de pruebas tiene correo de hoy, que cae dentro del rango.
  const sinResultados = /sin resultados/i.test(await pagina.locator('body').innerText());
  expect(sinResultados, 'el rango incluye hoy, así que debería encontrar el correo de hoy').toBe(false);
  expect(consulta, 'el rango debe ir con coma: nginx bloquea «..» en la URL').not.toContain('..');
});

test('buscar una palabra suelta responde al momento', async ({ sesion }) => {
  test.setTimeout(300_000);
  const { pagina } = sesion;
  await abrirCorreo(pagina);

  const caja = pagina.locator('#search-input');
  await caja.click();
  await caja.fill('factura');
  await pagina.keyboard.press('Enter');
  const r = await esperarResultados(pagina);
  await pagina.screenshot({ path: path.join(CAPTURAS, '4-palabra-suelta.png') });

  console.log(`   palabra suelta:      ${r.ms} ms, ${r.filas} filas, ¿error? ${r.hayError ? 'SÍ' : 'no'}`);
  expect(r.hayError).toBe(false);
  // Antes esto tardaba minuto y medio. Con un margen amplio para la red y el pintado.
  expect(r.ms, 'buscar una palabra no debería tardar más de 15 s').toBeLessThan(15_000);
});
