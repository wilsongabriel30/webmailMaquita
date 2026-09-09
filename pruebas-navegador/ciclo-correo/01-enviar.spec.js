// Mandar correo de verdad, como lo manda una persona, y comprobar que el correo existe después.
//
// Regla de esta tanda: **solo se tocan los mensajes que crea la propia prueba**, reconocibles por
// una marca única en el asunto. En este buzón hay correo de trabajo real; nada de lo que ya
// estaba se abre, se mueve ni se borra.
const fs = require('fs');
const path = require('path');
const { test, expect } = require('../pruebas/base');
const { abrirCorreo, USUARIO } = require('../pruebas/apoyo');

const CAPTURAS = path.join(__dirname, '..', 'capturas', 'correo-real');
fs.mkdirSync(CAPTURAS, { recursive: true });

const MARCA = `PRUEBA-${Date.now()}`;

// A dónde se escribe, por variable de entorno: aquí no se cablea ninguna dirección de nadie.
//   DESTINO_INTERNO=otra.cuenta@tu-dominio    (otra cuenta del mismo servidor)
//   DESTINO_EXTERNO=alguien@gmail.com         (fuera, para comprobar la salida)
// Sin ellas, esas dos pruebas se saltan y solo se prueba el envío a la propia cuenta.
const DESTINO_INTERNO = process.env.DESTINO_INTERNO || '';
const DESTINO_EXTERNO = process.env.DESTINO_EXTERNO || '';

/** Escribe un correo y lo envía. Devuelve el asunto usado. */
async function enviarA(pagina, destino, etiqueta) {
  const asunto = `${MARCA} ${etiqueta}`;
  await abrirCorreo(pagina);
  await pagina.getByRole('button', { name: /nuevo correo|redactar/i }).first().click();
  await pagina.waitForTimeout(1800);

  // El destinatario va en «Agregar destinatarios», no en el primer input de la pantalla: ese es
  // el buscador del correo, y escribir ahí deja el envío sin destinatario (la interfaz lo avisa
  // en rojo, con razón). Se identifica por su etiqueta, como haría una persona.
  const para = pagina.getByPlaceholder(/agregar destinatarios/i).first();
  await expect(para, 'no se encuentra el campo de destinatarios').toBeVisible({ timeout: 15_000 });
  await para.click();
  await pagina.keyboard.type(destino);
  await pagina.keyboard.press('Enter'); // Confirmar el destinatario como una etiqueta.
  await pagina.waitForTimeout(600);

  const campoAsunto = pagina.getByPlaceholder(/asunto/i).first();
  await campoAsunto.fill(asunto);

  const cuerpo = pagina.locator('[contenteditable="true"]').first();
  await cuerpo.click();
  await pagina.keyboard.type(`Correo de prueba enviado por el equipo de Tecnología. Marca: ${MARCA}. Puede borrarse.`);
  await pagina.waitForTimeout(300);

  await pagina.screenshot({ path: path.join(CAPTURAS, `${etiqueta}-1-antes-de-enviar.png`) });
  await pagina.getByRole('button', { name: /^Enviar$/ }).first().click();
  await pagina.waitForTimeout(3000);
  await pagina.screenshot({ path: path.join(CAPTURAS, `${etiqueta}-2-tras-enviar.png`) });

  // Si la interfaz se queja (destinatario vacío, adjunto pendiente…), el correo NO salió y
  // seguir comprobando carpetas solo daría un fallo confuso.
  const queja = await pagina.getByText(/ingresa un destinatario|falta el destinatario|destinatario/i)
    .first().isVisible().catch(() => false);
  expect(queja, `el redactor rechazó el envío a ${destino}: el correo no salió`).toBe(false);
  return asunto;
}

/** Busca un asunto en la carpeta indicada. Devuelve si aparece. */
async function apareceEn(pagina, carpeta, asunto, esperaMax = 60_000) {
  const limite = Date.now() + esperaMax;
  while (Date.now() < limite) {
    await pagina.getByText(carpeta).first().click().catch(() => {});
    await pagina.waitForTimeout(2500);
    if (await pagina.getByText(asunto, { exact: false }).first().count()) return true;
    await pagina.waitForTimeout(3000);
  }
  return false;
}

test.describe.configure({ mode: 'serial' });

test('enviar a la propia cuenta: sale, se guarda en Enviados y llega a la bandeja', async ({ sesion }) => {
  test.setTimeout(600_000);
  const { pagina } = sesion;

  const asunto = await enviarA(pagina, USUARIO, 'a-mi-mismo');
  console.log(`   asunto: ${asunto}`);

  const enEnviados = await apareceEn(pagina, /enviados|sent/i, asunto, 90_000);
  console.log(`   ¿está en Enviados?  ${enEnviados ? 'SÍ' : 'NO'}`);
  await pagina.screenshot({ path: path.join(CAPTURAS, 'a-mi-mismo-3-enviados.png') });
  expect(enEnviados, 'el correo enviado no aparece en Enviados').toBe(true);

  const enBandeja = await apareceEn(pagina, /entrada|recibidos|inbox/i, asunto, 120_000);
  console.log(`   ¿llegó a la bandeja?  ${enBandeja ? 'SÍ' : 'NO'}`);
  await pagina.screenshot({ path: path.join(CAPTURAS, 'a-mi-mismo-4-bandeja.png') });
  expect(enBandeja, 'el correo no llegó a la bandeja de entrada').toBe(true);

  // Y se tiene que poder leer: abrirlo y ver el cuerpo.
  await pagina.getByText(asunto, { exact: false }).first().click();
  await pagina.waitForTimeout(2500);
  const texto = await pagina.locator('body').innerText();
  await pagina.screenshot({ path: path.join(CAPTURAS, 'a-mi-mismo-5-leido.png') });
  expect(texto, 'el cuerpo del correo no se ve al abrirlo').toContain(MARCA);
  console.log('   se abre y se lee el cuerpo: SÍ');

  fs.writeFileSync(path.join(__dirname, '..', 'marca-prueba-correo.txt'), MARCA + '\n' + asunto + '\n');
});

test('enviar a otra cuenta del propio servidor', async ({ sesion }) => {
  test.setTimeout(600_000);
  test.skip(!DESTINO_INTERNO, 'sin DESTINO_INTERNO: no hay a quién escribir dentro del servidor');
  const { pagina } = sesion;
  const asunto = await enviarA(pagina, DESTINO_INTERNO, 'interno');
  const enEnviados = await apareceEn(pagina, /enviados|sent/i, asunto, 90_000);
  console.log(`   ${asunto} → ¿en Enviados?  ${enEnviados ? 'SÍ' : 'NO'}`);
  expect(enEnviados).toBe(true);
});

test('enviar fuera del servidor', async ({ sesion }) => {
  test.setTimeout(600_000);
  test.skip(!DESTINO_EXTERNO, 'sin DESTINO_EXTERNO: no se prueba la salida a internet');
  const { pagina } = sesion;
  const asunto = await enviarA(pagina, DESTINO_EXTERNO, 'externo');
  const enEnviados = await apareceEn(pagina, /enviados|sent/i, asunto, 90_000);
  console.log(`   ${asunto} → ¿en Enviados?  ${enEnviados ? 'SÍ' : 'NO'}`);
  expect(enEnviados).toBe(true);

  // Un rebote tarda; se mira la bandeja por si vuelve con error de entrega.
  await pagina.waitForTimeout(20_000);
  await pagina.getByText(/entrada|recibidos|inbox/i).first().click().catch(() => {});
  await pagina.waitForTimeout(3000);
  const texto = await pagina.locator('body').innerText();
  const rebote = /undeliverable|mail delivery|delivery status|no se pudo entregar|failure notice/i.test(texto);
  console.log(`   ¿rebote a la vista en la bandeja?  ${rebote ? 'SÍ — mirar' : 'no de momento'}`);
  await pagina.screenshot({ path: path.join(CAPTURAS, 'externo-3-bandeja-tras-envio.png') });
});
