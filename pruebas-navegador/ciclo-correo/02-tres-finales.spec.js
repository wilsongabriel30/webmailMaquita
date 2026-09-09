// «Me he equivocado»: los tres finales posibles de un envío con cuenta atrás.
//
// Al pulsar Enviar aparece «Enviando en Ns… Deshacer». De ahí salen tres caminos, y los tres
// importan:
//   1. Dejar que termine     → el correo tiene que salir.
//   2. Pulsar «Deshacer»     → el correo NO puede salir, y el borrador debe volver.
//   3. Cerrar la pestaña     → ¿sale, o se pierde en silencio? Es lo que hace una persona que
//                              se arrepiente y cierra, o que apaga el equipo sin más.
//
// Cada correo lleva un asunto único; después se comprueba en el registro del servidor si salió
// de verdad. La interfaz puede decir misa: lo que cuenta es si Postfix lo entregó.
const fs = require('fs');
const path = require('path');
const { test, expect } = require('../pruebas/base');
const { abrirCorreo, USUARIO } = require('../pruebas/apoyo');

const CAPTURAS = path.join(__dirname, '..', 'capturas', 'correo-real');
fs.mkdirSync(CAPTURAS, { recursive: true });
const SALIDA = path.join(__dirname, '..', 'asuntos-deshacer.json');
const asuntos = {};

async function escribir(pagina, destino, etiqueta) {
  const asunto = `PRUEBA-${Date.now()}-${etiqueta}`;
  await abrirCorreo(pagina);
  await pagina.getByRole('button', { name: /nuevo correo|redactar/i }).first().click();
  await pagina.waitForTimeout(1800);
  const para = pagina.getByPlaceholder(/agregar destinatarios/i).first();
  await para.click();
  await pagina.keyboard.type(destino);
  await pagina.keyboard.press('Enter');
  await pagina.waitForTimeout(500);
  await pagina.getByPlaceholder(/asunto/i).first().fill(asunto);
  const cuerpo = pagina.locator('[contenteditable="true"]').first();
  await cuerpo.click();
  await pagina.keyboard.type(`Prueba de la cuenta atrás de envío (${etiqueta}). Puede borrarse.`);
  await pagina.waitForTimeout(300);
  return asunto;
}

test.describe.configure({ mode: 'serial' });

test('1. dejar que la cuenta atrás termine: el correo sale', async ({ sesion }) => {
  test.setTimeout(300_000);
  const { pagina } = sesion;
  const asunto = await escribir(pagina, USUARIO, 'sale');
  await pagina.getByRole('button', { name: /^Enviar$/ }).first().click();

  // Esperar a que la cuenta atrás se agote del todo, sin tocar nada.
  await pagina.waitForTimeout(15_000);
  await pagina.screenshot({ path: path.join(CAPTURAS, 'deshacer-1-dejar-que-salga.png') });
  asuntos.sale = asunto;
  fs.writeFileSync(SALIDA, JSON.stringify(asuntos, null, 2));
  console.log(`   asunto que DEBE salir: ${asunto}`);
});

test('2. pulsar Deshacer: el correo no sale', async ({ sesion }) => {
  test.setTimeout(300_000);
  const { pagina } = sesion;
  const asunto = await escribir(pagina, USUARIO, 'deshecho');
  await pagina.getByRole('button', { name: /^Enviar$/ }).first().click();
  await pagina.waitForTimeout(700);

  const deshacer = pagina.getByRole('button', { name: /deshacer/i }).first();
  const hay = await deshacer.count() && await deshacer.isVisible().catch(() => false);
  console.log(`   ¿aparece el botón Deshacer?  ${hay ? 'SÍ' : 'NO'}`);
  expect(hay, 'no aparece «Deshacer» tras pulsar Enviar').toBe(true);

  await deshacer.click();
  await pagina.waitForTimeout(3000);
  await pagina.screenshot({ path: path.join(CAPTURAS, 'deshacer-2-tras-deshacer.png') });

  // Tras deshacer, lo esperable es recuperar el borrador para seguir editándolo.
  const vuelveElRedactor = await pagina.getByPlaceholder(/asunto/i).first().isVisible().catch(() => false);
  console.log(`   ¿vuelve el borrador a la pantalla?  ${vuelveElRedactor ? 'SÍ' : 'NO'}`);

  asuntos.deshecho = asunto;
  asuntos.vuelveElRedactor = vuelveElRedactor;
  fs.writeFileSync(SALIDA, JSON.stringify(asuntos, null, 2));
  console.log(`   asunto que NO debe salir: ${asunto}`);
  await pagina.waitForTimeout(15_000); // Por si el envío se disparara igualmente más tarde.
});

test('3. cerrar la pestaña durante la cuenta atrás: ¿sale o se pierde?', async ({ sesion, browser }) => {
  test.setTimeout(300_000);
  const { pagina } = sesion;
  const asunto = await escribir(pagina, USUARIO, 'pestana-cerrada');
  await pagina.getByRole('button', { name: /^Enviar$/ }).first().click();
  await pagina.waitForTimeout(1200); // Con la cuenta atrás corriendo…

  // …la persona se va: se navega a otra página, que es lo que pasa al cerrar la pestaña.
  await pagina.goto('about:blank');
  await pagina.waitForTimeout(2000);
  await pagina.goto('/webmail/', { waitUntil: 'domcontentloaded' }).catch(() => {});
  await pagina.waitForTimeout(4000);
  await pagina.screenshot({ path: path.join(CAPTURAS, 'deshacer-3-tras-cerrar.png') });

  asuntos.pestanaCerrada = asunto;
  fs.writeFileSync(SALIDA, JSON.stringify(asuntos, null, 2));
  console.log(`   asunto con la pestaña cerrada a media cuenta atrás: ${asunto}`);
  await pagina.waitForTimeout(10_000);
});
