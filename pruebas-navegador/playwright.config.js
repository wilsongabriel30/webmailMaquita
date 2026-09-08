// Pruebas con navegador de verdad, como una persona delante de la pantalla.
//
// Nada está cableado a nuestra instalación: dirección y credenciales llegan por variables de
// entorno, así que cualquiera puede correrlas contra la suya.
//
//   WEBMAIL_URL=https://correo.ejemplo.org \
//   PRUEBAS_USUARIO=buzon@ejemplo.org PRUEBAS_CLAVE=... \
//   npx playwright test
//
// Se entra UNA vez y las demás pruebas reutilizan esa sesión: entrar en cada prueba choca
// contra el límite de intentos del propio correo (429), que hace bien su trabajo.
const { defineConfig } = require('@playwright/test');

module.exports = defineConfig({
  testDir: './pruebas',
  timeout: 60_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  retries: 0,
  reporter: [['list']],
  use: {
    baseURL: process.env.WEBMAIL_URL || 'https://localhost',
    headless: true,
    screenshot: 'only-on-failure',
    video: 'off',
    actionTimeout: 15_000,
    locale: 'es-EC',
  },
  workers: 1,
  projects: [{ name: 'chromium', use: { browserName: 'chromium' } }],
});
