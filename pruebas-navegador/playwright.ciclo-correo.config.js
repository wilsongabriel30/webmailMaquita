// EL CICLO DEL CORREO: estas pruebas ENVÍAN CORREO DE VERDAD y mueven mensajes a la papelera.
//
// Por eso viven aparte y no se corren con las demás. Úsalas con un buzón dedicado, nunca con la
// cuenta de una persona: escriben a sí mismas y, si se les indica, a otra cuenta del servidor y
// a una dirección de fuera.
//
//   WEBMAIL_URL=https://correo.ejemplo.org PRUEBAS_USUARIO=buzon.pruebas@ejemplo.org \
//   PRUEBAS_CLAVE=... [DESTINO_INTERNO=...] [DESTINO_EXTERNO=...] \
//     npx playwright test -c playwright.ciclo-correo.config.js
//
// Lo que comprueban de verdad no es la pantalla: es el registro del servidor. Cada correo lleva
// un asunto único («PRUEBA-<marca de tiempo>») para poder buscarlo después:
//
//   grep "Mailbox Sent: save.*PRUEBA-1788964195217" /var/log/mail.log
const { defineConfig } = require('@playwright/test');
const base = require('./playwright.config');

module.exports = defineConfig({
  ...base,
  testDir: './ciclo-correo',
  timeout: 900_000,
  reporter: [['list']],
});
