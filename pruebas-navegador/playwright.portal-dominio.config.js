// Recorrido del portal de administradores de dominio con navegador de verdad.
//
//   PORTAL_URL=https://correo.ejemplo.org:8444 PORTAL_DOMINIO=ejemplo.org \
//   PORTAL_USUARIO=admin-ejemplo PORTAL_CLAVE='la clave inicial' \
//   npx playwright test -c playwright.portal-dominio.config.js
//
// La cuenta debe estar recién creada (con su clave inicial): el recorrido empieza por el
// cambio de clave obligatorio. Crea cuentas y alias de prueba en PORTAL_DOMINIO; úsese un
// dominio de pruebas.
const { defineConfig } = require('@playwright/test');

module.exports = defineConfig({
  testDir: './portal-dominio',
  timeout: 60_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [['list']],
  use: {
    baseURL: process.env.PORTAL_URL || 'https://localhost:8444',
    headless: true,
    ignoreHTTPSErrors: process.env.PRUEBAS_TLS_LAXA === '1',
    screenshot: 'only-on-failure',
    actionTimeout: 10_000,
    locale: 'es-EC',
  },
  projects: [{ name: 'chromium', use: { browserName: 'chromium' } }],
});
