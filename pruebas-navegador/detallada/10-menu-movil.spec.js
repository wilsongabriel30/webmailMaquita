// Como se comporta el menu de pulsacion larga en un telefono.
const { test, expect, devices } = require('@playwright/test');

const URL = process.env.WEBMAIL_URL;
const USUARIO = process.env.PRUEBAS_USUARIO;
const CLAVE = process.env.PRUEBAS_CLAVE;

test('menu contextual en pantalla de telefono', async ({ browser }) => {
  test.setTimeout(240_000);
  const ctx = await browser.newContext({ ...devices['Pixel 5'], ignoreHTTPSErrors: true });
  const pagina = await ctx.newPage();
  await pagina.goto(`${URL}/webmail/`);
  await pagina.locator('input').first().fill(USUARIO);
  await pagina.locator('input[type="password"]').fill(CLAVE);
  await pagina.locator('button[type="submit"]').click();
  await pagina.waitForTimeout(12000);

  const { width: ancho, height: alto } = pagina.viewportSize();
  console.log(`   pantalla del telefono: ${ancho}x${alto}`);

  const filas = pagina.locator('div[draggable="true"]');
  const total = await filas.count();
  console.log(`   correos visibles: ${total}`);
  if (total === 0) { console.log('   sin correos: no se puede probar'); await ctx.close(); return; }

  // Chrome en Android lanza `contextmenu` al mantener pulsado; se reproduce ese evento
  // sobre la ultima fila, que es el caso que se cortaba.
  const fila = filas.nth(total - 1);
  await fila.scrollIntoViewIfNeeded();
  const caja = await fila.boundingBox();
  await fila.dispatchEvent('contextmenu', {
    clientX: Math.round(caja.x + 40),
    clientY: Math.round(caja.y + caja.height - 2),
    bubbles: true,
  });
  await pagina.waitForTimeout(600);

  const menu = pagina.locator('div[class*="shadow-xl"][class*="min-w"]').last();
  const visible = await menu.isVisible().catch(() => false);
  console.log(`   el menu se abre en el telefono: ${visible ? 'SI' : 'NO'}`);
  if (visible) {
    const m = await menu.boundingBox();
    console.log(`   menu: ${Math.round(m.x)},${Math.round(m.y)} de ${Math.round(m.width)}x${Math.round(m.height)} (pantalla ${ancho}x${alto})`);
    expect(m.x).toBeGreaterThanOrEqual(-1);
    expect(m.y).toBeGreaterThanOrEqual(-1);
    expect(m.x + m.width).toBeLessThanOrEqual(ancho + 1);
    expect(m.y + m.height).toBeLessThanOrEqual(alto + 1);
    console.log('   cabe entero en la pantalla del telefono');
  }
  await ctx.close();
});
