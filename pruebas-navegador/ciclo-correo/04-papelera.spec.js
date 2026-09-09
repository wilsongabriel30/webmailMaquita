// Borrar y recuperar, aceptando los diálogos del navegador.
//
// El borrado pide confirmación con `window.confirm`, y un navegador automatizado responde
// «cancelar» si nadie le dice lo contrario: por eso parecía que el botón no hacía nada. Aquí se
// acepta el diálogo, como haría la persona que pulsa «Aceptar».
//
// Se opera SOLO sobre correos con asunto «PRUEBA-»: en este buzón hay correo de trabajo real.
const path = require('path');
const fs = require('fs');
const { test, expect } = require('../pruebas/base');
const { abrirCorreo } = require('../pruebas/apoyo');

const CAPTURAS = path.join(__dirname, '..', 'capturas', 'correo-real');
fs.mkdirSync(CAPTURAS, { recursive: true });

test('eliminar un correo de prueba y recuperarlo de la papelera', async ({ sesion }) => {
  test.setTimeout(600_000);
  const { pagina } = sesion;

  const dialogos = [];
  pagina.on('dialog', async (d) => { dialogos.push(d.message()); await d.accept(); });

  await abrirCorreo(pagina);
  const objetivo = pagina.getByText(/^PRUEBA-\d+/).first();
  expect(await objetivo.count(), 'no hay correos de prueba en la bandeja').toBeGreaterThan(0);
  const asunto = (await objetivo.innerText()).trim().split('\n')[0];
  console.log(`   correo de prueba: ${asunto}`);

  // Marcarlo en la lista: es lo que la barra de herramientas necesita para actuar.
  await objetivo.hover();
  await pagina.waitForTimeout(400);
  await objetivo.click();
  await pagina.waitForTimeout(1500);

  const casillas = pagina.locator('input[type="checkbox"]:visible');
  const cuantas = await casillas.count();
  // La primera es «seleccionar todo»; la del mensaje es la que está en su fila.
  for (let i = 1; i < cuantas; i++) {
    const c = casillas.nth(i);
    const suyo = await c.evaluate((el) => el.closest('[class*="group"], li, tr, div')?.innerText || '').catch(() => '');
    if (suyo.includes(asunto.slice(0, 20))) { await c.check().catch(() => {}); break; }
  }
  await pagina.waitForTimeout(800);
  await pagina.screenshot({ path: path.join(CAPTURAS, 'ok-1-marcado.png') });

  await pagina.getByRole('button', { name: /^Eliminar/i }).first().click({ timeout: 5000 }).catch(() => {});
  await pagina.waitForTimeout(3500);
  console.log(`   diálogos que salieron: ${dialogos.join(' | ') || 'ninguno'}`);
  await pagina.screenshot({ path: path.join(CAPTURAS, 'ok-2-tras-eliminar.png') });

  // ¿Está en la papelera?
  await pagina.getByText(/papelera|trash/i).first().click().catch(() => {});
  await pagina.waitForTimeout(3000);
  const enPapelera = await pagina.getByText(asunto, { exact: false }).first().count();
  console.log(`   ¿está en la papelera?  ${enPapelera ? 'SÍ' : 'NO'}`);
  await pagina.screenshot({ path: path.join(CAPTURAS, 'ok-3-papelera.png') });
  expect(enPapelera, 'el correo eliminado no llegó a la papelera').toBeGreaterThan(0);

  // Recuperarlo: desde la papelera, moverlo de vuelta a la bandeja.
  const enLaPapelera = pagina.getByText(asunto, { exact: false }).first();
  await enLaPapelera.click();
  await pagina.waitForTimeout(1500);
  const casillas2 = pagina.locator('input[type="checkbox"]:visible');
  for (let i = 1; i < await casillas2.count(); i++) {
    const c = casillas2.nth(i);
    const suyo = await c.evaluate((el) => el.closest('[class*="group"], li, tr, div')?.innerText || '').catch(() => '');
    if (suyo.includes(asunto.slice(0, 20))) { await c.check().catch(() => {}); break; }
  }
  await pagina.waitForTimeout(600);

  let recuperado = false;
  const restaurar = pagina.getByRole('button', { name: /restaurar|recuperar/i }).first();
  if (await restaurar.count() && await restaurar.isVisible().catch(() => false)) {
    await restaurar.click(); recuperado = true;
    console.log('   recuperado con «Restaurar»');
  } else {
    const mover = pagina.getByRole('button', { name: /^Mover/i }).first();
    if (await mover.count()) {
      await mover.click();
      await pagina.waitForTimeout(1200);
      await pagina.screenshot({ path: path.join(CAPTURAS, 'ok-4-menu-mover.png') });
      const destino = pagina.getByText(/^Bandeja de entrada$|^INBOX$/i).last();
      if (await destino.count()) { await destino.click().catch(() => {}); recuperado = true; }
      console.log('   recuperado con «Mover a → Bandeja de entrada»');
    }
  }
  await pagina.waitForTimeout(3500);
  await pagina.screenshot({ path: path.join(CAPTURAS, 'ok-5-tras-recuperar.png') });
  expect(recuperado, 'desde la papelera no hay forma visible de recuperar el correo').toBe(true);

  await pagina.getByText(/entrada|recibidos|inbox/i).first().click().catch(() => {});
  await pagina.waitForTimeout(3000);
  const vuelto = await pagina.getByText(asunto, { exact: false }).first().count();
  console.log(`   ¿ha vuelto a la bandeja?  ${vuelto ? 'SÍ' : 'NO'}`);
  await pagina.screenshot({ path: path.join(CAPTURAS, 'ok-6-de-vuelta.png') });
  fs.writeFileSync(path.join(__dirname, '..', 'papelera-resultado.json'),
    JSON.stringify({ asunto, dialogos, enPapelera: !!enPapelera, recuperado, vuelto: !!vuelto }, null, 2));
  expect(vuelto, 'el correo recuperado no vuelve a la bandeja').toBeGreaterThan(0);
});
