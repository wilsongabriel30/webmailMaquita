// Las herramientas de redacción, usadas como las usa una persona: escribir, seleccionar y darle
// al botón. No basta con que el botón no reviente: el texto tiene que quedar en negrita de
// verdad. Aquí se comprueba el RESULTADO en el cuerpo del mensaje, no el clic.
//
// Nada se envía: la prueba termina con el borrador abierto y lo cierra sin guardar.
const { test, expect } = require('../pruebas/base');
const { abrirCorreo } = require('../pruebas/apoyo');
const { observar } = require('./observador');
const { anotar, volcar } = require('./informe');

test.describe.configure({ mode: 'serial' });

const FRASE = 'Texto de prueba para dar formato';

/** Selecciona el contenido del cuerpo, como quien arrastra el ratón sobre lo escrito.
 *  `Control+A` no vale: selecciona la página entera y el formato se queda sin sobre qué actuar,
 *  con lo que la prueba acusaba de rotas herramientas que funcionan. */
async function seleccionarCuerpo(cuerpo) {
  await cuerpo.evaluate((el) => {
    const rango = document.createRange();
    rango.selectNodeContents(el);
    const seleccion = window.getSelection();
    seleccion.removeAllRanges();
    seleccion.addRange(rango);
  });
}

/** Abre el redactor y devuelve el elemento del cuerpo, ya con una frase escrita y seleccionada. */
async function abrirRedactorConTexto(pagina) {
  await abrirCorreo(pagina);
  await pagina.getByRole('button', { name: /nuevo correo|redactar|escribir/i }).first().click();
  await pagina.waitForTimeout(1500);

  const cuerpo = pagina.locator('[contenteditable="true"]').first();
  await expect(cuerpo, 'el redactor no ofrece un cuerpo donde escribir').toBeVisible({ timeout: 20_000 });
  await cuerpo.click();
  await pagina.keyboard.type(FRASE);
  await pagina.waitForTimeout(300);
  await seleccionarCuerpo(cuerpo);
  return cuerpo;
}

// Cada herramienta con la huella que debe dejar en el cuerpo. Si el botón no está, se anota:
// una herramienta anunciada y ausente es tan problema como una rota.
// Los nombres son los que el navegador ve de verdad (`inventario-redactor.json`): la cinta usa
// las letras sueltas B, I, U, S, sin título ni etiqueta. Que se llamen así ya es un hallazgo,
// anotado aparte; aquí lo que se comprueba es si HACEN lo que prometen.
const FORMATOS = [
  { nombre: /^B$/, deja: /<(b|strong)[ >]|font-weight:\s*(bold|[6-9]00)/i, que: 'negrita (B)' },
  { nombre: /^I$/, deja: /<(i|em)[ >]|font-style:\s*italic/i, que: 'cursiva (I)' },
  { nombre: /^U$/, deja: /<u[ >]|text-decoration[^;"]*underline/i, que: 'subrayado (U)' },
  { nombre: /^S$/, deja: /<(s|strike)[ >]|line-through/i, que: 'tachado (S)' },
  { nombre: /^A$/, deja: /color:\s*[^;"]+/i, que: 'color de fuente (A)' },
  { nombre: /^ab$/, deja: /background(-color)?:\s*[^;"]+/i, que: 'resaltado (ab)' },
  { nombre: /^Borrar formato$/, deja: /./, que: 'borrar formato' },
];

test('las herramientas de formato dejan huella en el texto', async ({ sesion }) => {
  test.setTimeout(600_000);
  const { pagina } = sesion;
  const ojo = observar(pagina);

  for (const formato of FORMATOS) {
    const cuerpo = await abrirRedactorConTexto(pagina);
    ojo.cosecha();

    // La cinta tiene pestañas; el formato vive en «Aplicar formato».
    const pestana = pagina.getByRole('button', { name: /^Aplicar formato$/ }).first();
    if (await pestana.count()) await pestana.click({ timeout: 4000 }).catch(() => {});
    await pagina.waitForTimeout(500);
    await seleccionarCuerpo(cuerpo);

    const boton = pagina.getByRole('button', { name: formato.nombre, exact: true }).first();
    const existe = await boton.count() && await boton.isVisible().catch(() => false);
    if (!existe) {
      anotar('baja', 'Redactor', `no se encuentra la herramienta «${formato.que}»`,
        'puede estar en una pestaña de la cinta que no está abierta');
      await pagina.keyboard.press('Escape').catch(() => {});
      continue;
    }

    await boton.click({ timeout: 5000 }).catch(() => {});
    await pagina.waitForTimeout(600);

    const html = await cuerpo.innerHTML().catch(() => '');
    if (!formato.deja.test(html)) {
      anotar('alta', 'Redactor', `«${formato.que}» no cambia el texto`,
        'el botón responde pero el cuerpo del mensaje queda igual');
    } else {
      console.log(`   · ${formato.que}: aplica`);
    }

    const visto = ojo.cosecha();
    for (const e of visto.excepciones) anotar('alta', 'Redactor', `«${formato.que}» revienta la página`, e);
    for (const f of visto.fallidas) {
      anotar(/^5\d\d/.test(f) ? 'alta' : 'media', 'Redactor', `«${formato.que}» deja una petición fallida`, f);
    }
    await pagina.keyboard.press('Escape').catch(() => {});
  }

  volcar();
  expect(true).toBe(true);
});

test('el redactor acepta lo básico: destinatario, asunto y cuerpo', async ({ sesion }) => {
  test.setTimeout(300_000);
  const { pagina } = sesion;
  const ojo = observar(pagina);
  await abrirRedactorConTexto(pagina);

  // Destinatario: el campo tiene que aceptar una dirección y conservarla.
  const para = pagina.locator('input[type="text"]:visible, input[type="email"]:visible').first();
  await para.fill('destino@ejemplo.org').catch(() => {});
  const valorPara = await para.inputValue().catch(() => '');
  if (!valorPara.includes('destino@ejemplo.org')) {
    anotar('alta', 'Redactor', 'el campo de destinatario no conserva lo escrito', `quedó «${valorPara}»`);
  }

  // Asunto: se busca por su etiqueta, como haría una persona.
  const asunto = pagina.getByPlaceholder(/asunto/i).first();
  if (await asunto.count()) {
    await asunto.fill('Prueba de interfaz (no se envía)').catch(() => {});
    const v = await asunto.inputValue().catch(() => '');
    if (!v) anotar('alta', 'Redactor', 'el campo de asunto no conserva lo escrito', '');
  } else {
    anotar('media', 'Redactor', 'no se encuentra el campo de asunto por su etiqueta',
      'quien navega con lector de pantalla no lo localiza');
  }

  const visto = ojo.cosecha();
  for (const e of visto.excepciones) anotar('alta', 'Redactor', 'excepción al rellenar el borrador', e);
  for (const f of visto.fallidas) {
    anotar(/^5\d\d/.test(f) ? 'alta' : 'media', 'Redactor', 'petición fallida al rellenar el borrador', f);
  }

  await pagina.keyboard.press('Escape').catch(() => {});
  volcar();
  expect(true).toBe(true);
});
