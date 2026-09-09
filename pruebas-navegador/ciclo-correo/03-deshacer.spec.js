// «Deshacer», el del aviso de envío — no el de la cinta.
//
// En el redactor hay DOS botones que se llaman «Deshacer»: el del portapapeles (deshace lo que
// escribiste) y el del aviso «Enviando en Ns…» (cancela el envío). Apuntar al primero por
// descuido haría acusar al producto de algo que no hace. Aquí se busca dentro del aviso.
const fs = require('fs');
const path = require('path');
const { test, expect } = require('../pruebas/base');
const { abrirCorreo, USUARIO } = require('../pruebas/apoyo');

const CAPTURAS = path.join(__dirname, '..', 'capturas', 'correo-real');
fs.mkdirSync(CAPTURAS, { recursive: true });

test('pulsar el Deshacer del aviso de envío cancela el correo', async ({ sesion }) => {
  test.setTimeout(300_000);
  const { pagina } = sesion;
  const asunto = `PRUEBA-${Date.now()}-deshacer-del-aviso`;

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
  await pagina.keyboard.type('Este correo NO debería salir: se cancela desde el aviso.');

  await pagina.getByRole('button', { name: /^Enviar$/ }).first().click();
  await pagina.waitForTimeout(800);

  // El aviso: el trozo de pantalla que dice «Enviando en …». El «Deshacer» que vale es el suyo.
  const aviso = pagina.locator('div', { hasText: /Enviando en \d+s/ }).last();
  await expect(aviso, 'no aparece el aviso «Enviando en Ns…»').toBeVisible({ timeout: 10_000 });
  await pagina.screenshot({ path: path.join(CAPTURAS, 'aviso-1-cuenta-atras.png') });

  const botonDeshacer = aviso.getByText(/deshacer/i).last();
  await botonDeshacer.click({ timeout: 5000 });
  await pagina.waitForTimeout(2500);
  await pagina.screenshot({ path: path.join(CAPTURAS, 'aviso-2-tras-deshacer.png') });

  const textoTras = await pagina.locator('body').innerText();
  console.log(`   ¿sigue la cuenta atrás?  ${/Enviando en \d+s/.test(textoTras) ? 'SÍ' : 'no'}`);
  console.log(`   ¿vuelve el borrador?     ${/Agregar un asunto|${asunto}/.test(textoTras) ? 'SÍ' : 'NO'}`);

  fs.writeFileSync(path.join(__dirname, '..', 'asunto-deshacer-aviso.txt'), asunto + '\n');
  console.log(`   asunto que NO debe salir: ${asunto}`);

  // Esperar de sobra por si el envío se dispara igual pasada la cuenta atrás.
  await pagina.waitForTimeout(20_000);
});
