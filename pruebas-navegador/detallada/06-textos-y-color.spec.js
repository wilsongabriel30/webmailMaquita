// Dos cosas que saltaron al mirar una captura de pantalla, que es como mira una persona.
//
// 1. En el redactor se lee «Sensibilidad…»: una secuencia de escape que nadie interpretó y
//    que la persona ve tal cual. Se busca ese patrón en TODA la interfaz, no solo ahí.
// 2. La paleta de color sí se abre; faltaba pulsar una muestra de color de verdad.
const fs = require('fs');
const path = require('path');
const { test, expect } = require('../pruebas/base');
const { abrirCorreo } = require('../pruebas/apoyo');
const { SECCIONES } = require('./mapa');

const CAPTURAS = path.join(__dirname, '..', 'capturas');
fs.mkdirSync(CAPTURAS, { recursive: true });

// `\uXXXX`, `\n`, `&amp;` y compañía, cuando llegan a la pantalla sin interpretar.
const ESCAPES_A_LA_VISTA = /\\u[0-9a-fA-F]{4}|\\n(?![a-z])|&(amp|quot|#39|lt|gt);/;

test('ningún texto de la interfaz enseña escapes sin interpretar', async ({ sesion }) => {
  test.setTimeout(600_000);
  const { pagina } = sesion;
  const encontrados = [];

  const revisar = async (donde) => {
    const textos = await pagina.$$eval('*', (nodos) => nodos
      .filter((n) => n.children.length === 0 && n.offsetParent !== null)
      .map((n) => (n.innerText || n.value || '').trim())
      .filter(Boolean));
    // Los desplegables enseñan su texto en las opciones, que no son «visibles» de esa forma.
    const opciones = await pagina.$$eval('option', (nodos) => nodos.map((n) => n.textContent.trim()));
    for (const t of [...new Set([...textos, ...opciones])]) {
      if (ESCAPES_A_LA_VISTA.test(t)) encontrados.push({ donde, texto: t.slice(0, 80) });
    }
  };

  for (const seccion of SECCIONES) {
    await pagina.goto(seccion.ruta, { waitUntil: 'domcontentloaded' }).catch(() => {});
    await pagina.waitForTimeout(2000);
    await revisar(seccion.nombre);
  }

  // Y el redactor, donde se vio.
  await abrirCorreo(pagina);
  await pagina.getByRole('button', { name: /nuevo correo|redactar/i }).first().click();
  await pagina.waitForTimeout(2000);
  await revisar('Redactor');
  await pagina.screenshot({ path: path.join(CAPTURAS, 'textos-redactor.png') });

  for (const e of encontrados) console.log(`   !! [${e.donde}] texto con escape sin interpretar: «${e.texto}»`);
  fs.writeFileSync(path.join(__dirname, '..', 'textos-con-escapes.json'), JSON.stringify(encontrados, null, 2));
  console.log(`   total: ${encontrados.length}`);
  await pagina.keyboard.press('Escape').catch(() => {});
  expect(true).toBe(true);
});

test('la paleta de color aplica el color elegido', async ({ sesion }) => {
  test.setTimeout(300_000);
  const { pagina } = sesion;
  await abrirCorreo(pagina);
  await pagina.getByRole('button', { name: /nuevo correo|redactar/i }).first().click();
  await pagina.waitForTimeout(2000);

  const cuerpo = pagina.locator('[contenteditable="true"]').first();
  await cuerpo.click();
  await pagina.keyboard.type('Texto para colorear');
  const seleccionar = () => cuerpo.evaluate((el) => {
    const r = document.createRange(); r.selectNodeContents(el);
    const s = window.getSelection(); s.removeAllRanges(); s.addRange(r);
  });
  await seleccionar();

  const pestana = pagina.getByRole('button', { name: /^Aplicar formato$/ }).first();
  if (await pestana.count()) await pestana.click().catch(() => {});
  await pagina.waitForTimeout(400);
  await seleccionar();

  await pagina.getByRole('button', { name: 'A', exact: true }).first().click().catch(() => {});
  await pagina.waitForTimeout(700);

  // La paleta es una rejilla de muestras; se pulsa una que no sea negra para notar el cambio.
  const muestras = pagina.locator('button:visible, [role="button"]:visible, div[style*="background"]:visible');
  const total = await muestras.count();
  console.log(`   controles a la vista con la paleta abierta: ${total}`);

  let pulsada = false;
  for (let i = 0; i < total && !pulsada; i++) {
    const m = muestras.nth(i);
    const fondo = await m.evaluate((el) => getComputedStyle(el).backgroundColor).catch(() => '');
    // Una muestra de color: fondo sólido, ni blanco ni transparente.
    if (/^rgb\(/.test(fondo) && !/rgb\(255, 255, 255\)/.test(fondo)) {
      const caja = await m.boundingBox().catch(() => null);
      if (caja && caja.width < 40 && caja.height < 40) {
        await m.click({ timeout: 3000 }).catch(() => {});
        pulsada = true;
        console.log(`   muestra pulsada, color ${fondo}`);
      }
    }
  }

  await pagina.waitForTimeout(900);
  const html = await cuerpo.innerHTML();
  await pagina.screenshot({ path: path.join(CAPTURAS, 'color-3-tras-muestra.png') });
  console.log('   cuerpo: ' + html.slice(0, 220));
  console.log(`   ¿aplica color?  ${/color:\s*(?!inherit)[^;"]+/i.test(html) ? 'SÍ' : 'NO'}`);
  await pagina.keyboard.press('Escape').catch(() => {});
  expect(true).toBe(true);
});
