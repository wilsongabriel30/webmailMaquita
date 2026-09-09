// ¿El botón Enviar manda el correo de verdad? Se mira la petición, no el texto de la pantalla.
//
// Importante: el envío es DIFERIDO. Al pulsar Enviar sale un aviso «Enviando en 5s… Deshacer» y
// el `POST /mail/send` solo sale al cumplirse esos 5 segundos. Una prueba que mire antes concluye
// —en falso— que el botón no hace nada.
const { test, expect } = require('./base');
const { abrirCorreo, USUARIO } = require('./apoyo');

test('pulsar Enviar manda el correo y llega a la bandeja', async ({ sesion }) => {
  const { pagina } = sesion;
  const peticiones = [];
  pagina.on('request', (r) => {
    if (r.method() !== 'GET' && r.url().includes('/api/')) peticiones.push(`${r.method()} ${new URL(r.url()).pathname}`);
  });
  const respuestas = [];
  pagina.on('response', (r) => {
    if (r.request().method() !== 'GET' && r.url().includes('/api/')) {
      respuestas.push(`${r.status()} ${new URL(r.url()).pathname}`);
    }
  });

  const marca = `Prueba de interfaz ${Date.now()}`;

  await abrirCorreo(pagina);
  await pagina.getByRole('button', { name: /^Correo$/ }).first().click();
  await pagina.waitForTimeout(800);
  await pagina.getByRole('button', { name: /nuevo correo/i }).first().click();
  await pagina.waitForTimeout(1500);

  await pagina.getByPlaceholder(/destinatarios/i).first().fill(USUARIO);
  await pagina.waitForTimeout(400);
  await pagina.keyboard.press('Enter');            // fijar el destinatario, como haría una persona
  await pagina.getByPlaceholder(/asunto/i).first().fill(marca);
  const cuerpo = pagina.locator('[contenteditable="true"]:visible').first();
  await cuerpo.click();
  await cuerpo.type('Texto de prueba.');
  peticiones.length = 0; respuestas.length = 0;

  const enviar = pagina.getByRole('button', { name: /^enviar$/i }).first();
  // La espera se arma ANTES de pulsar: si se arma después, el envío ya ocurrió y no se ve.
  const esperaEnvio = pagina.waitForResponse(
    (r) => r.url().includes('/api/mail/send') && r.request().method() === 'POST',
    { timeout: 20000 },
  ).catch(() => null);
  await enviar.click();

  // La cuenta atrás, tal como la ve la persona, segundo a segundo.
  const cuentaAtras = [];
  for (let i = 0; i < 6; i++) {
    const aviso = await pagina.locator('text=/Enviando en \\d+s/').first().innerText().catch(() => null);
    if (aviso) cuentaAtras.push(aviso.trim());
    await pagina.waitForTimeout(1000);
  }
  const vistos = [...new Set(cuentaAtras)];
  console.log('   cuenta atrás vista:', JSON.stringify(vistos));
  // El aviso promete una cuenta atrás; si se queda clavado en «5s» la persona no sabe cuánto
  // le queda para arrepentirse.
  expect(vistos.length, 'la cuenta atrás debe bajar, no quedarse en 5s').toBeGreaterThan(1);

  const envio = await esperaEnvio;
  console.log('   respuesta del envío:', envio ? `${envio.status()} ${new URL(envio.url()).pathname}` : 'NO HUBO');
  console.log('   peticiones tras pulsar:', JSON.stringify(peticiones));
  console.log('   respuestas:', JSON.stringify(respuestas));

  expect(envio, 'el botón Enviar debe acabar mandando POST /api/mail/send').not.toBeNull();
  expect(envio.status(), 'el envío debe responder correctamente').toBeLessThan(400);

  // ¿Llegó? Es un correo a la propia cuenta: debe aparecer en la bandeja.
  let llego = false;
  for (let i = 0; i < 12 && !llego; i++) {
    await pagina.waitForTimeout(5000);
    await pagina.reload();
    await pagina.waitForTimeout(2500);
    llego = await pagina.locator(`text=${marca}`).first().isVisible().catch(() => false);
  }
  console.log('   ¿llegó el correo a la bandeja?', llego);
  await pagina.screenshot({ path: 'informe/al-enviar.png' });
  expect(llego, 'el correo enviado a la propia cuenta debe aparecer en la bandeja').toBe(true);
});
