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
    // Evaluaciones con certificado propio (la guia de instalacion las contempla):
    //   PRUEBAS_TLS_LAXA=1 npx playwright test
    //
    // `ignoreHTTPSErrors` no alcanza al *service worker*: su fetch nace fuera del contexto y
    // el recorrido de entrada fallaba pese a la variable (aviso de Andes, 09/09/2026). Bajo
    // TLS laxo se bloquea el worker, que no hace falta para lo que prueban estos recorridos.
    ignoreHTTPSErrors: process.env.PRUEBAS_TLS_LAXA === '1',
    serviceWorkers: process.env.PRUEBAS_TLS_LAXA === '1' ? 'block' : 'allow',
    screenshot: 'only-on-failure',
    video: 'off',
    actionTimeout: 15_000,
    locale: 'es-EC',
  },
  workers: 1,
  projects: [{ name: 'chromium', use: { browserName: 'chromium' } }],
});
