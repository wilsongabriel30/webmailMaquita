// Exploración de la interfaz: recorre las secciones y pulsa lo que encuentra.
//
// Es una tanda aparte de las pruebas de regresión: aquí se BUSCAN fallos, no se fijan. Escribe
// un informe con lo que ve y no da por bueno nada por sí sola: lo que levanta hay que mirarlo
// de cerca (para eso está `50-verificar`).
//
//   WEBMAIL_URL=https://correo.ejemplo.org PRUEBAS_USUARIO=... PRUEBAS_CLAVE=... \
//     npx playwright test -c playwright.exploracion.config.js
const { defineConfig } = require('@playwright/test');
const base = require('./playwright.config');

module.exports = defineConfig({
  ...base,
  testDir: './exploracion',
  timeout: 1_200_000,
  reporter: [['list']],
});
