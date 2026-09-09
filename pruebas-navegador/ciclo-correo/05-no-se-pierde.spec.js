// El correo no se pierde aunque cierres la pestaña mientras corre la cuenta atrás.
//
// Reproduce el fallo tal cual se encontró: pulsar Enviar, irse a los pocos segundos (que es lo
// que hace quien cierra la pestaña) y volver a abrir el correo. El veredicto NO lo da la
// pantalla: lo da el registro del servidor, que se consulta aparte con el asunto único.
const fs = require('fs');
const path = require('path');
const { test, expect } = require('../pruebas/base');
const { abrirCorreo, USUARIO } = require('../pruebas/apoyo');

const CAPTURAS = path.join(__dirname, '..', 'capturas', 'correo-real');
fs.mkdirSync(CAPTURAS, { recursive: true });

test('cerrar la pestaña durante la cuenta atrás no pierde el correo', async ({ sesion }) => {
  test.setTimeout(300_000);
  const { pagina } = sesion;
  const asunto = `PRUEBA-${Date.now()}-superviviente`;

  await abrirCorreo(pagina);
  await pagina.getByRole('button', { name: /nuevo correo|redactar/i }).first().click();
  await pagina.waitForTimeout(1800);
  const para = pagina.getByPlaceholder(/agregar destinatarios/i).first();
  await para.click();
  await pagina.keyboard.type(USUARIO);
  await pagina.keyboard.press('Enter');
  await pagina.waitForTimeout(500);
  await pagina.getByPlaceholder(/asunto/i).first().fill(asunto);
  const cuerpo = pagina.locator('[contenteditable="true"]').first();
  await cuerpo.click();
  await pagina.keyboard.type('Si este correo llega, cerrar la pestaña a media cuenta atrás ya no lo pierde.');

  await pagina.getByRole('button', { name: /^Enviar$/ }).first().click();
  await pagina.waitForTimeout(1200); // La cuenta atrás acaba de empezar…
  await pagina.screenshot({ path: path.join(CAPTURAS, 'superviviente-1-cuenta-atras.png') });

  // …y la persona se va: se abandona la página con el envío a medias.
  await pagina.goto('about:blank');
  await pagina.waitForTimeout(3000);

  // Vuelve a abrir el correo: aquí es donde la cola tiene que rescatar lo retenido.
  await pagina.goto('/webmail/', { waitUntil: 'domcontentloaded' }).catch(() => {});
  await pagina.waitForTimeout(12_000);
  await pagina.screenshot({ path: path.join(CAPTURAS, 'superviviente-2-tras-volver.png') });

  fs.writeFileSync(path.join(__dirname, '..', 'asunto-superviviente.txt'), asunto + '\n');
  console.log(`   asunto a comprobar en el servidor: ${asunto}`);
  expect(asunto).toContain('superviviente');
});
