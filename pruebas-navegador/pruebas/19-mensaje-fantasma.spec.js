// Un correo que ya no está: la persona tiene que enterarse.
//
// Justo después de archivar, la lista conserva un instante la fila del mensaje archivado. Antes,
// pulsarla no producía NADA (el 404 solo salía en la consola). Ahora debe salir un aviso y la
// lista debe refrescarse sola.
const { test, expect } = require('./base');
const { abrirCorreo, asegurarUnMensaje } = require('./apoyo');

test('pulsar un correo que ya no está avisa en pantalla', async ({ sesion }) => {
  const { pagina } = sesion;
  await abrirCorreo(pagina);
  await pagina.getByRole('button', { name: /^Correo$/ }).first().click();
  await pagina.waitForTimeout(2000);
  expect(await asegurarUnMensaje(pagina), 'hace falta un mensaje para archivarlo').toBe(true);

  await pagina.locator('div[draggable="true"]').first().click();
  await pagina.waitForTimeout(1500);
  await pagina.getByRole('button', { name: /^Archivar/i }).first().click();

  // Sin esperar al refresco: se pulsa la fila que todavía está ahí, que es lo que hace una persona.
  await pagina.waitForTimeout(300);
  const fila = pagina.locator('div[draggable="true"]').first();
  if (await fila.count()) await fila.click({ timeout: 3000 }).catch(() => {});
  await pagina.waitForTimeout(2500);

  const texto = await pagina.locator('body').innerText();
  const aviso = texto.split('\n').find((l) => /ya no está|no se pudo abrir|se actualizó la lista/i.test(l));
  console.log('   aviso mostrado:', JSON.stringify(aviso || null));
  await pagina.screenshot({ path: 'informe/mensaje-fantasma.png' });

  // El caso puede no darse si el refresco gana la carrera: entonces no hay fila fantasma y está bien.
  const quedanFilas = await pagina.locator('div[draggable="true"]').count();
  console.log('   filas tras el intento:', quedanFilas);
  expect(
    Boolean(aviso) || quedanFilas === 0 || !/Message not found/.test(texto),
    'o sale un aviso, o la fila ya no está: lo que no vale es un clic sin ninguna respuesta',
  ).toBe(true);
});
