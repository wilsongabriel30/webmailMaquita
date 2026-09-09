// El recorrido de siempre de una persona: escribir, enviar, recibir, leer y actuar sobre el correo.
// Se usa la cuenta de pruebas escribiéndose a sí misma: no se molesta a nadie.
const { test, expect } = require('./base');
const { vigilar, abrirCorreo, USUARIO } = require('./apoyo');

const ASUNTO = 'Prueba de interfaz ' + Date.now();

test('escribir y enviar un correo', async ({ sesion }) => {
  const { pagina } = sesion;
  const ojo = vigilar(pagina);
  await abrirCorreo(pagina);
  await pagina.getByRole('button', { name: /^Correo$/ }).first().click();
  await pagina.waitForTimeout(1000);
  await pagina.getByRole('button', { name: /nuevo correo|redactar/i }).first().click();
  await pagina.waitForTimeout(1500);

  await pagina.getByPlaceholder(/destinatarios/i).first().fill(USUARIO);
  await pagina.waitForTimeout(400);
  await pagina.keyboard.press('Enter');            // fijar el destinatario, como haría una persona
  await pagina.getByPlaceholder(/asunto/i).first().fill(ASUNTO);
  const cuerpo = pagina.locator('[contenteditable="true"]:visible').first();
  await cuerpo.click();
  await cuerpo.type('Mensaje de prueba de la revisión de interfaz. Se puede borrar.');

  const enviar = pagina.getByRole('button', { name: /^enviar/i }).first();
  console.log('   ¿hay botón Enviar?', await enviar.count() > 0);
  // El envío es diferido 5 segundos (ventana de «Deshacer»): la espera se arma ANTES de pulsar y
  // se comprueba la peticion real, no el texto de la pantalla (donde «Enviados» ya casa con
  // cualquier patron parecido y daria un falso positivo).
  const esperaEnvio = pagina.waitForResponse(
    (r) => r.url().includes('/api/mail/send') && r.request().method() === 'POST',
    { timeout: 25_000 },
  ).catch(() => null);
  await enviar.click();
  const envio = await esperaEnvio;
  console.log('   respuesta del envío:', envio ? envio.status() : 'NO HUBO');
  expect(envio, 'el correo no llegó a enviarse').not.toBeNull();
  expect(envio.status()).toBeLessThan(400);
  console.log('   fallidas al enviar:', ojo.fallidas.length ? [...new Set(ojo.fallidas)].join(' | ') : 'ninguna');
  await pagina.screenshot({ path: 'informe/tras-enviar.png' });
});

test('el correo llega, se abre y se puede actuar sobre él', async ({ sesion }) => {
  const { pagina } = sesion;
  const ojo = vigilar(pagina);
  await abrirCorreo(pagina);
  await pagina.getByRole('button', { name: /^Correo$/ }).first().click();

  // Esperar a que llegue (entrega local, suele ser inmediata)
  let llego = false;
  for (let i = 0; i < 10 && !llego; i++) {
    await pagina.waitForTimeout(3000);
    await pagina.reload();
    await pagina.waitForTimeout(2500);
    llego = (await pagina.getByText(ASUNTO).count()) > 0;
  }
  console.log('   ¿llegó el correo a la bandeja?', llego);
  expect(llego, 'el correo enviado no aparece en la bandeja').toBe(true);

  await pagina.getByText(ASUNTO).first().click();
  await pagina.waitForTimeout(2000);
  const lectura = await pagina.locator('body').innerText();
  console.log('   ¿se ve el cuerpo del mensaje?', lectura.includes('revisión de interfaz'));
  await pagina.screenshot({ path: 'informe/mensaje-abierto.png' });

  const acciones = ['Responder', 'Archivar', 'Eliminar', 'Marcar', 'Leído', 'Mover', 'Imprimir'];
  const estado = [];
  for (const a of acciones) {
    const b = pagina.getByRole('button', { name: new RegExp(`^${a}`, 'i') }).first();
    const hay = await b.count() > 0;
    const activo = hay ? await b.isEnabled().catch(() => false) : false;
    estado.push(`${a}: ${hay ? (activo ? 'disponible' : 'DESHABILITADO') : 'NO ESTÁ'}`);
  }
  console.log('   acciones sobre el mensaje:\n     ' + estado.join('\n     '));
  console.log('   fallidas:', ojo.fallidas.length ? [...new Set(ojo.fallidas)].join(' | ') : 'ninguna');
});
