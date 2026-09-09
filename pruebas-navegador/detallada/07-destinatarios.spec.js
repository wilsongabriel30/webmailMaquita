// Que el redactor no deje salir un correo hacia una dirección que no existe.
//
// Nace de un aviso del equipo de Andes (09/09/2026). Al reproducirlo resultó peor de lo que
// contaban: con el campo Para vacío sí avisaba, pero con una dirección MAL ESCRITA no avisaba
// nada y arrancaba la cuenta atrás igualmente — el correo se daba por enviado hacia algo que no
// es una dirección. Misma familia que el correo que se perdía al cerrar la pestaña: el sistema
// se calla y alguien cree que mandó lo que no salió.
//
// Se prueban los dos casos por separado, porque se comportaban distinto, y se mira lo que mira
// una persona: si aparece algo, si está a la vista sin desplazar, y si sigue ahí un rato después
// (un aviso que se desvanece en dos segundos es como no tenerlo).
const fs = require('fs');
const path = require('path');
const { test, expect } = require('../pruebas/base');
const { abrirCorreo } = require('../pruebas/apoyo');

const CAPTURAS = path.join(__dirname, '..', 'capturas', 'destinatarios');
fs.mkdirSync(CAPTURAS, { recursive: true });

const PALABRAS_DE_AVISO = /destinatario|ingresa|falta|requerid|obligatorio|no es una direcci|no son válidas/i;

async function abrirRedactorConTexto(pagina) {
  await abrirCorreo(pagina);
  await pagina.getByRole('button', { name: /nuevo correo|redactar/i }).first().click();
  await pagina.waitForTimeout(1800);
  await pagina.getByPlaceholder(/asunto/i).first().fill('Prueba: enviar sin destinatario válido');
  const cuerpo = pagina.locator('[contenteditable="true"]').first();
  await cuerpo.click();
  await pagina.keyboard.type('Este correo no debería poder enviarse.');
  await pagina.waitForTimeout(300);
}

/** ¿Hay algún aviso a la vista? Devuelve qué se ve y si está en pantalla sin desplazar. */
async function mirarAviso(pagina) {
  const textos = await pagina.$$eval('*', (nodos, patron) => nodos
    .filter((n) => n.children.length === 0 && n.offsetParent !== null)
    .map((n) => (n.innerText || '').trim())
    .filter((t) => new RegExp(patron, 'i').test(t)), PALABRAS_DE_AVISO.source);
  let enPantalla = false;
  if (textos.length) {
    const el = pagina.getByText(textos[0], { exact: false }).first();
    // No basta con que exista en el árbol: tiene que estar dentro de la parte visible.
    enPantalla = await el.evaluate((n) => {
      const r = n.getBoundingClientRect();
      return r.top >= 0 && r.bottom <= (window.innerHeight || 0) && r.width > 0;
    }).catch(() => false);
  }
  return { textos: [...new Set(textos)], enPantalla };
}

test.describe.configure({ mode: 'serial' });

test('con el campo Para vacío avisa, y el aviso se queda', async ({ sesion }) => {
  test.setTimeout(300_000);
  const { pagina } = sesion;
  await abrirRedactorConTexto(pagina);

  await pagina.getByRole('button', { name: /^Enviar$/ }).first().click();
  await pagina.waitForTimeout(1200);
  const alInstante = await mirarAviso(pagina);
  await pagina.screenshot({ path: path.join(CAPTURAS, 'vacio-al-instante.png') });

  await pagina.waitForTimeout(8000);
  const pasados9s = await mirarAviso(pagina);
  await pagina.screenshot({ path: path.join(CAPTURAS, 'vacio-nueve-segundos.png') });

  console.log(`   Para vacío, al instante: ${JSON.stringify(alInstante)}`);
  console.log(`   Para vacío, a los 9 s:   ${JSON.stringify(pasados9s)}`);

  expect(alInstante.enPantalla, 'debería avisar de que falta el destinatario').toBe(true);
  expect(pasados9s.enPantalla, 'el aviso no debería desvanecerse solo').toBe(true);
  await pagina.keyboard.press('Escape').catch(() => {});
});

test('con una dirección mal escrita avisa y NO envía', async ({ sesion }) => {
  test.setTimeout(300_000);
  const { pagina } = sesion;
  await abrirRedactorConTexto(pagina);

  const para = pagina.getByPlaceholder(/agregar destinatarios/i).first();
  await para.click();
  await pagina.keyboard.type('esto-no-es-una-direccion');
  await pagina.keyboard.press('Enter');
  await pagina.waitForTimeout(700);

  await pagina.getByRole('button', { name: /^Enviar$/ }).first().click();
  await pagina.waitForTimeout(1500);
  const aviso = await mirarAviso(pagina);
  await pagina.screenshot({ path: path.join(CAPTURAS, 'mal-escrita-tras-enviar.png') });

  // Lo grave no era la falta de aviso, sino que el correo salía igualmente.
  const hayCuentaAtras = /Enviando en \d+s/.test(await pagina.locator('body').innerText());
  console.log(`   Dirección mal escrita, aviso: ${JSON.stringify(aviso)}`);
  console.log(`   ¿arranca la cuenta atrás?     ${hayCuentaAtras ? 'SÍ' : 'no'}`);

  expect(hayCuentaAtras, 'no debe iniciarse el envío con una dirección inválida').toBe(false);
  expect(aviso.enPantalla, 'debería avisar de que la dirección no vale').toBe(true);
  expect(aviso.textos.join(' '), 'el aviso debería nombrar la dirección que falla')
    .toContain('esto-no-es-una-direccion');
  await pagina.keyboard.press('Escape').catch(() => {});
});
