// Recorridos de persona, a fondo, sobre un buzón con correo dentro: leer, responder, moverse
// por el calendario, mirar los ajustes. No envía, no borra y no guarda nada.
//
//   WEBMAIL_URL=https://correo.ejemplo.org PRUEBAS_USUARIO=... PRUEBAS_CLAVE=... \
//     npx playwright test -c playwright.detallada.config.js
const { defineConfig } = require('@playwright/test');
const base = require('./playwright.config');

module.exports = defineConfig({
  ...base,
  testDir: './detallada',
  timeout: 900_000,
  reporter: [['list']],
});
