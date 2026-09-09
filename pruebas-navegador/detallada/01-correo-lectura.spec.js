// Leer correo de verdad: abrir mensajes reales del buzón, verlos enteros y usar lo que ofrece
// la pantalla de lectura. Nada que envíe, borre ni mueva nada: solo leer y abrir paneles.
const path = require('path');
const fs = require('fs');
const { test, expect } = require('../pruebas/base');
const { abrirCorreo } = require('../pruebas/apoyo');
const { observar } = require('../exploracion/observador');
const { anotar, volcar } = require('../exploracion/informe');

const CAPTURAS = path.join(__dirname, '..', 'capturas', 'detallada');
fs.mkdirSync(CAPTURAS, { recursive: true });

test.describe.configure({ mode: 'serial' });

test('abrir varios correos seguidos y verlos enteros', async ({ sesion }) => {
  test.setTimeout(600_000);
  const { pagina } = sesion;
  const ojo = observar(pagina);
  await abrirCorreo(pagina);
  ojo.cosecha();

  const filas = pagina.locator('div[draggable="true"]');
  const cuantos = Math.min(await filas.count(), 5);
  expect(cuantos, 'el buzón no tiene correos que leer').toBeGreaterThan(0);
  console.log(`   correos en la bandeja: ${await filas.count()} (se abren ${cuantos})`);

  for (let i = 0; i < cuantos; i++) {
    await filas.nth(i).click();
    await pagina.waitForTimeout(2500);

    const texto = (await pagina.locator('body').innerText()).trim();
    // Un correo abierto tiene que enseñar de quién es y cuándo llegó.
    if (!/@/.test(texto)) {
      anotar('alta', 'Lectura', `el correo ${i + 1} se abre sin mostrar remitente`, '');
    }
    const visto = ojo.cosecha();
    for (const e of visto.excepciones) anotar('alta', 'Lectura', `abrir el correo ${i + 1} revienta la página`, e);
    for (const f of visto.fallidas) {
      anotar(/^5\d\d/.test(f) ? 'alta' : 'media', 'Lectura', `abrir el correo ${i + 1} deja una petición fallida`, f);
    }
  }
  await pagina.screenshot({ path: path.join(CAPTURAS, 'lectura-1-correo-abierto.png') });
  volcar();
});

test('lo que ofrece un correo abierto: responder, reenviar, origen, imprimir', async ({ sesion }) => {
  test.setTimeout(600_000);
  const { pagina } = sesion;
  const ojo = observar(pagina);
  await abrirCorreo(pagina);
  await pagina.locator('div[draggable="true"]').first().click();
  await pagina.waitForTimeout(2500);
  ojo.cosecha();

  // Responder y reenviar abren el redactor con el correo citado. No se envía nada.
  for (const accion of [/^responder$/i, /responder a todos/i, /^reenviar$/i]) {
    const boton = pagina.getByRole('button', { name: accion }).first();
    if (!(await boton.count())) {
      anotar('media', 'Lectura', `no aparece «${accion}» con un correo abierto`, '');
      continue;
    }
    await boton.click({ timeout: 6000 }).catch(() => {});
    await pagina.waitForTimeout(2000);

    // Ojo con cómo se comprueba: al RESPONDER el destinatario ya viene puesto, así que el
    // hueco «Agregar destinatarios» no está. Buscarlo daba por roto un redactor que funciona.
    // Se mira lo que sí define un redactor abierto: cuerpo donde escribir y botón de enviar.
    const cuerpo = await pagina.locator('[contenteditable="true"]').count();
    const enviar = await pagina.getByRole('button', { name: /^Enviar$/ }).count();
    if (!cuerpo || !enviar) {
      anotar('alta', 'Lectura', `«${accion}» no abre el redactor`,
        `cuerpo editable: ${cuerpo}, botón enviar: ${enviar}`);
    } else {
      console.log(`   ${accion}: abre el redactor`);
    }
    const visto = ojo.cosecha();
    for (const e of visto.excepciones) anotar('alta', 'Lectura', `«${accion}» revienta la página`, e);

    // Cerrar el borrador sin guardar y volver al correo.
    await pagina.keyboard.press('Escape').catch(() => {});
    await pagina.waitForTimeout(800);
    await abrirCorreo(pagina);
    await pagina.locator('div[draggable="true"]').first().click();
    await pagina.waitForTimeout(1500);
    ojo.cosecha();
  }

  // Ver el origen del mensaje: es lo que pide soporte cuando algo no cuadra.
  const origen = pagina.getByRole('button', { name: /ver origen|origen del mensaje/i }).first();
  if (await origen.count()) {
    await origen.click({ timeout: 6000 }).catch(() => {});
    await pagina.waitForTimeout(2000);
    const texto = (await pagina.locator('body').innerText());
    if (!/Received:|Return-Path|Message-ID|DKIM/i.test(texto)) {
      anotar('media', 'Lectura', '«Ver origen del mensaje» no enseña las cabeceras', '');
    } else {
      console.log('   ver origen: enseña las cabeceras');
    }
    await pagina.screenshot({ path: path.join(CAPTURAS, 'lectura-2-origen.png') });
    await pagina.keyboard.press('Escape').catch(() => {});
  } else {
    anotar('baja', 'Lectura', 'no se ve «Ver origen del mensaje»', '');
  }

  const visto = ojo.cosecha();
  for (const f of visto.fallidas) {
    anotar(/^5\d\d/.test(f) ? 'alta' : 'media', 'Lectura', 'petición fallida al usar el correo abierto', f);
  }
  volcar();
});
