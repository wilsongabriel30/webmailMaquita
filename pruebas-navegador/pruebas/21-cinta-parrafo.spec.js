// Grupo «Párrafo» de la pestaña Mensaje del redactor (components/compose/GrupoParrafo.tsx, 28/10/2026):
// viñetas, numeración, sangría, estilos, cita, alinear, espaciado y dirección del texto. Se aplica cada
// opción, se envía el correo a la propia cuenta y se comprueba que el formato llega igual.
const { test, expect } = require('./base');
const { vigilar, abrirCorreo, sinPeticionesFallidas, USUARIO } = require('./apoyo');

const ASUNTO = 'Prueba grupo Párrafo ' + Date.now();

const html = (pagina) => pagina.locator('.tiptap[contenteditable="true"]').first().innerHTML();

async function escribirParrafo(pagina, texto, primero = false) {
  if (!primero) await pagina.keyboard.press('Enter');
  await pagina.keyboard.type(texto);
}

test('el grupo Párrafo aplica sus opciones y el formato llega al destinatario', async ({ sesion }) => {
  test.setTimeout(240_000);
  const { pagina } = sesion;
  const ojo = vigilar(pagina);
  await abrirCorreo(pagina);
  await pagina.getByRole('button', { name: /^Correo$/ }).first().click();
  await pagina.getByRole('button', { name: /nuevo correo|redactar/i }).first().click();
  await pagina.waitForTimeout(1500);

  // El grupo está en la cinta, con su etiqueta y todos sus botones.
  await expect(pagina.getByText('Párrafo', { exact: true }).first()).toBeVisible();
  const boton = (nombre) => pagina.getByRole('button', { name: nombre, exact: true }).first();
  for (const n of ['Viñetas', 'Numeración', 'Disminuir sangría', 'Aumentar sangría', 'Estilos: da a tus mensajes un formato pulido',
    'Cita', 'Alinear', 'Espaciado entre líneas y párrafos', 'De izquierda a derecha', 'De derecha a izquierda']) {
    await expect(boton(n), `falta el botón «${n}»`).toBeVisible();
  }
  await pagina.screenshot({ path: 'informe/parrafo-cinta.png', clip: { x: 0, y: 0, width: 1280, height: 260 } });

  await pagina.getByPlaceholder(/destinatarios/i).first().fill(USUARIO);
  await pagina.waitForTimeout(400);
  await pagina.keyboard.press('Enter');
  await pagina.getByPlaceholder(/asunto/i).first().fill(ASUNTO);
  const cuerpo = pagina.locator('.tiptap[contenteditable="true"]').first();
  await cuerpo.click();
  await pagina.keyboard.press('Control+Home');

  // 1. Sangría de párrafo (dos niveles y uno menos).
  await escribirParrafo(pagina, 'Párrafo con sangría', true);
  await boton('Aumentar sangría').click();
  await boton('Aumentar sangría').click();
  await boton('Disminuir sangría').click();
  expect(await html(pagina)).toContain('margin-left: 40px');

  // 2. Centrado + interlineado 1,5 + espacio antes y después.
  await escribirParrafo(pagina, 'Párrafo centrado con interlineado');
  await boton('Disminuir sangría').click(); // el párrafo nuevo hereda la sangría, como en Outlook: se quita
  await boton('Alinear').click();
  await pagina.getByRole('menuitem', { name: /centrar/i }).click();
  await boton('Espaciado entre líneas y párrafos').click();
  await pagina.getByRole('menuitem', { name: '1,5' }).click();
  await boton('Espaciado entre líneas y párrafos').click();
  await pagina.getByRole('menuitem', { name: /agregar espacio antes/i }).click();
  await boton('Espaciado entre líneas y párrafos').click();
  await pagina.getByRole('menuitem', { name: /agregar espacio después/i }).click();
  let h = await html(pagina);
  expect(h).toMatch(/text-align: center[^"]*line-height: 1\.5[^"]*margin-top: 12px[^"]*margin-bottom: 12px/);

  // El menú marca lo que ya tiene el párrafo y cambia su texto a «Quitar…».
  await boton('Espaciado entre líneas y párrafos').click();
  await expect(pagina.getByRole('menuitem', { name: /quitar espacio antes/i })).toBeVisible();
  await pagina.screenshot({ path: 'informe/parrafo-menu-espaciado.png' });
  await pagina.keyboard.press('Escape');
  await pagina.mouse.click(5, 5);

  // 3. De derecha a izquierda.
  await cuerpo.click();
  await pagina.keyboard.press('Control+End');
  await pagina.keyboard.press('Enter'); // el párrafo nuevo hereda centrado y espaciado: se le quitan a él
  await boton('Alinear').click();
  await pagina.getByRole('menuitem', { name: /alinear a la izquierda/i }).click();
  await boton('Espaciado entre líneas y párrafos').click();
  await pagina.getByRole('menuitem', { name: '1,0' }).click();
  await boton('Espaciado entre líneas y párrafos').click();
  await pagina.getByRole('menuitem', { name: /quitar espacio antes/i }).click();
  await boton('Espaciado entre líneas y párrafos').click();
  await pagina.getByRole('menuitem', { name: /quitar espacio después/i }).click();
  await pagina.keyboard.type('Párrafo de derecha a izquierda');
  await boton('De derecha a izquierda').click();
  await expect(boton('De derecha a izquierda')).toHaveAttribute('aria-pressed', 'true');
  expect(await html(pagina)).toMatch(/<p dir="rtl"[^>]*>Párrafo de derecha a izquierda/);

  // 4. Viñetas con un elemento anidado, y numeración.
  await escribirParrafo(pagina, 'Viñeta uno');
  await boton('De izquierda a derecha').click();
  await boton('Viñetas').click();
  await escribirParrafo(pagina, 'Viñeta anidada');
  await boton('Aumentar sangría').click();
  await pagina.keyboard.press('Enter'); await pagina.keyboard.press('Enter'); await pagina.keyboard.press('Enter');
  await boton('Numeración').click();
  await pagina.keyboard.type('Número uno');
  await pagina.keyboard.press('Enter'); await pagina.keyboard.press('Enter');

  // 5. Cita y estilo Título 2.
  await boton('Cita').click();
  await pagina.keyboard.type('Texto citado');
  await pagina.keyboard.press('Enter'); await pagina.keyboard.press('Enter');
  await boton('Estilos: da a tus mensajes un formato pulido').click();
  await pagina.getByRole('menuitem', { name: 'Título 2' }).click();
  await pagina.keyboard.type('Un título');

  h = await html(pagina);
  console.log('   HTML del redactor:', h);
  expect(h).toMatch(/<ul><li><p>Viñeta uno<\/p><ul><li><p>Viñeta anidada/);
  expect(h).toMatch(/<ol><li><p>Número uno/);
  expect(h).toMatch(/<blockquote><p>Texto citado/);
  expect(h).toMatch(/<h2[^>]*>Un título<\/h2>/);
  await pagina.screenshot({ path: 'informe/parrafo-redactor.png' });

  // Enviar a la propia cuenta.
  const esperaEnvio = pagina.waitForResponse(
    (r) => r.url().includes('/api/mail/send') && r.request().method() === 'POST', { timeout: 25_000 }).catch(() => null);
  await pagina.getByRole('button', { name: /^enviar/i }).first().click();
  const envio = await esperaEnvio;
  expect(envio, 'el correo no llegó a enviarse').not.toBeNull();
  expect(envio.status()).toBeLessThan(400);

  // Recibirlo y comprobar que el formato llegó igual.
  let llego = false;
  for (let i = 0; i < 10 && !llego; i++) {
    await pagina.waitForTimeout(3000);
    await pagina.reload();
    await pagina.waitForTimeout(2500);
    llego = (await pagina.getByText(ASUNTO).count()) > 0;
  }
  expect(llego, 'el correo enviado no aparece en la bandeja').toBe(true);
  await pagina.getByText(ASUNTO).first().click();
  await pagina.waitForTimeout(3000);

  let recibido = '';
  for (const marco of pagina.frames()) {
    recibido = await marco.evaluate(() => {
      const p = [...document.querySelectorAll('p')].find((e) => e.textContent?.includes('Párrafo centrado con interlineado'));
      return p ? p.closest('div,body').innerHTML : '';
    }).catch(() => '');
    if (recibido) break;
  }
  console.log('   HTML recibido:', recibido.slice(0, 1500));
  expect(recibido, 'no se encontró el cuerpo del correo recibido').not.toBe('');
  expect(recibido).toContain('margin-left: 40px');
  expect(recibido).toMatch(/text-align: center[^"]*line-height: 1\.5/);
  expect(recibido).toMatch(/dir="rtl"/);
  expect(recibido).toMatch(/<blockquote/);
  await pagina.screenshot({ path: 'informe/parrafo-recibido.png' });

  sinPeticionesFallidas(ojo.fallidas, 'grupo Párrafo');
});

// Reporte 28/10/2026: con sangría, al poner viñetas o numeración el símbolo se quedaba en el margen y el
// texto se iba a la derecha. Como en Outlook, la sangría debe mover la lista entera (símbolo junto al texto).
test('con sangría, las viñetas y los números salen junto al texto', async ({ sesion }) => {
  const { pagina } = sesion;
  await abrirCorreo(pagina);
  await pagina.getByRole('button', { name: /^Correo$/ }).first().click();
  await pagina.getByRole('button', { name: /nuevo correo|redactar/i }).first().click();
  await pagina.waitForTimeout(1500);
  const boton = (nombre) => pagina.getByRole('button', { name: nombre, exact: true }).first();
  const cuerpo = pagina.locator('.tiptap[contenteditable="true"]').first();
  await cuerpo.click();
  await pagina.keyboard.press('Control+Home');
  for (const [i, t] of ['hola', 'hola', 'hola'].entries()) {
    if (i) await pagina.keyboard.press('Enter');
    await pagina.keyboard.type(t);
  }
  await pagina.keyboard.press('Control+Home');
  for (let i = 0; i < 2; i++) await pagina.keyboard.press('Shift+ArrowDown');
  await pagina.keyboard.press('Shift+End');
  await boton('Aumentar sangría').click();
  await boton('Aumentar sangría').click();
  await boton('Viñetas').click();
  await expect(boton('Viñetas')).toHaveAttribute('aria-pressed', 'true');
  let html = await cuerpo.innerHTML();
  expect(html).toMatch(/<ul style="margin-left: 80px;"><li><p>hola<\/p><\/li>/);
  expect(html).not.toMatch(/<li><p style="margin-left/);

  // En pantalla: la viñeta queda a menos de 30 px del texto (antes, unos 120 px).
  const distancia = await pagina.evaluate(() => {
    const li = document.querySelector('.tiptap ul > li');
    const p = li.querySelector('p');
    const marcador = parseFloat(getComputedStyle(li, '::marker').fontSize) || 0;
    const ul = li.parentElement.getBoundingClientRect();
    return { texto: p.getBoundingClientRect().left - ul.left, marcador };
  });
  console.log('   separación entre el borde de la lista y el texto:', distancia.texto, 'px');
  expect(distancia.texto).toBeLessThan(60);
  await pagina.screenshot({ path: 'informe/parrafo-vinetas-con-sangria.png' });

  // Cambiar a numeración conserva la sangría.
  await boton('Numeración').click();
  await expect(boton('Numeración')).toHaveAttribute('aria-pressed', 'true');
  await expect(boton('Viñetas')).toHaveAttribute('aria-pressed', 'false');
  html = await cuerpo.innerHTML();
  expect(html).toMatch(/<ol style="margin-left: 80px;">/);
  await pagina.screenshot({ path: 'informe/parrafo-numeracion-con-sangria.png' });

  // Escribir «- » al inicio de un párrafo con sangría también crea la lista desplazada.
  await pagina.keyboard.press('Control+End');
  await pagina.keyboard.press('Enter'); await pagina.keyboard.press('Enter');
  await boton('Aumentar sangría').click();
  await pagina.keyboard.type('- guion');
  html = await cuerpo.innerHTML();
  expect(html).toMatch(/<ul style="margin-left: 40px;"><li><p>guion<\/p>/);
});
