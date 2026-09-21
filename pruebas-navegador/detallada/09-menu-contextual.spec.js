// El menú de clic derecho tiene que verse entero, también al abrirlo pegado al borde de abajo:
// antes se dibujaba siempre hacia abajo desde el cursor y las últimas opciones quedaban fuera.
const { test, expect } = require('../pruebas/base');
const { abrirCorreo } = require('../pruebas/apoyo');

test('el menú de clic derecho se ve entero en cualquier punto de la bandeja', async ({ sesion }) => {
  test.setTimeout(300_000);
  const { pagina } = sesion;
  await abrirCorreo(pagina);

  const filas = pagina.locator('div[draggable="true"]');
  const total = await filas.count();
  expect(total, 'el buzón no tiene correos donde hacer clic derecho').toBeGreaterThan(0);

  const { width: ancho, height: alto } = pagina.viewportSize();
  const menu = pagina.locator('div[class*="shadow-xl"][class*="min-w"]').last();
  const aProbar = [...new Set([total - 1, Math.floor(total / 2), 0])].filter((i) => i >= 0);

  for (const indice of aProbar) {
    const fila = filas.nth(indice);
    await fila.scrollIntoViewIfNeeded();
    const caja = await fila.boundingBox();
    if (!caja) continue;

    // Lo más abajo posible dentro de la fila: es donde antes se cortaba.
    await fila.click({ button: 'right', position: { x: 40, y: Math.max(1, caja.height - 2) } });
    await pagina.waitForTimeout(400);
    await expect(menu).toBeVisible();

    const m = await menu.boundingBox();
    console.log(
      `   fila ${indice}: clic en y=${Math.round(caja.y + caja.height)} · menú ${Math.round(m.y)}→${Math.round(m.y + m.height)} de ${alto}px`,
    );
    expect(m.y, 'el menú se sale por arriba').toBeGreaterThanOrEqual(-1);
    expect(m.x, 'el menú se sale por la izquierda').toBeGreaterThanOrEqual(-1);
    expect(m.y + m.height, 'el menú se sale por abajo').toBeLessThanOrEqual(alto + 1);
    expect(m.x + m.width, 'el menú se sale por la derecha').toBeLessThanOrEqual(ancho + 1);

    await pagina.keyboard.press('Escape');
    await pagina.waitForTimeout(250);
  }
});
