// Una sola sesión para toda la tanda, como una persona que entra por la mañana y trabaja.
//
// Por qué: cada prueba con su propia sesión chocaba contra dos cosas reales del producto, y
// hacía bien en chocar: el límite de intentos de entrada (429 tras varios seguidos) y la
// renovación del vale, que invalida el anterior y dejaba a las pruebas siguientes con uno viejo.
const base = require('@playwright/test');
const { entrar, apartarAvisos } = require('./apoyo');

const test = base.test.extend({
  // Contexto y página compartidos por todo el proceso de pruebas.
  sesion: [
    async ({ browser }, usar) => {
      const contexto = await browser.newContext({ locale: 'es-EC' });
      const pagina = await contexto.newPage();
      await entrar(pagina);
      await apartarAvisos(pagina);
      await usar({ contexto, pagina });
      await contexto.close();
    },
    { scope: 'worker' },
  ],
});

module.exports = { test, expect: base.expect };
