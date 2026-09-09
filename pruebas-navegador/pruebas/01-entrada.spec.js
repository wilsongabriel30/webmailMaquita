// La pantalla de entrada, tal como la ve alguien que aún no ha entrado.
const { test, expect } = require('@playwright/test');
const { vigilar, sinPeticionesFallidas } = require('./apoyo');

test('la pantalla de entrada carga limpia', async ({ page }) => {
  const ojo = vigilar(page);
  await page.goto('/webmail/login', { waitUntil: 'networkidle' });
  await expect(page.locator('input[type="password"]')).toBeVisible();
  expect(ojo.consola, 'errores en la consola al cargar la entrada').toEqual([]);
  sinPeticionesFallidas(ojo.fallidas, 'peticiones fallidas al cargar la entrada');
});
