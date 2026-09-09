// Las acciones sobre un mensaje: ¿cada botón hace algo, y algo que se note?
//
// No basta con que el botón exista y no reviente. Aquí se pulsa cada uno con un mensaje abierto y
// se mira lo que la persona vería: una petición al servidor, un aviso, un diálogo, un cambio en la
// lista. Un botón que no produce NADA de eso es un botón roto aunque la consola esté limpia.
const { test, expect } = require('./base');
const { abrirCorreo, vigilar, asegurarUnMensaje } = require('./apoyo');

// Acciones de la cinta que operan sobre el mensaje seleccionado.
const ACCIONES = [
  { nombre: 'Responder', patron: /^Responder/i, espera: 'ventana' },
  { nombre: 'Marcar', patron: /^Marcar/i, espera: 'algo' },
  { nombre: 'Leído', patron: /^Leído|^Leido|no le[ií]do/i, espera: 'algo' },
  { nombre: 'Archivar', patron: /^Archivar/i, espera: 'algo' },
  { nombre: 'Mover', patron: /^Mover/i, espera: 'menu' },
  { nombre: 'Clasificar', patron: /^Clasificar/i, espera: 'menu' },
  { nombre: 'Posponer', patron: /^Posponer/i, espera: 'menu' },
];

test('cada acción sobre un mensaje produce algo visible', async ({ sesion }) => {
  const { pagina } = sesion;
  const { consola } = vigilar(pagina);

  await abrirCorreo(pagina);
  await pagina.getByRole('button', { name: /^Correo$/ }).first().click();
  await pagina.waitForTimeout(1200);

  // Abrir el primer mensaje de la bandeja. Sin mensaje seleccionado, media cinta está apagada
  // a propósito y la prueba no diría nada.
  expect(await asegurarUnMensaje(pagina), 'hace falta al menos un mensaje para probar las acciones').toBe(true);
  await pagina.locator('div[draggable="true"]').first().click();
  await pagina.waitForTimeout(1500);

  const resultados = [];
  for (const accion of ACCIONES) {
    // Escape (que se usa para cerrar lo que abrió la acción anterior) también deja de lado el
    // mensaje, así que se vuelve a abrir uno antes de cada acción.
    // Archivar y Eliminar vacían la bandeja: cada acción se abastece de su propio mensaje.
    if (!(await asegurarUnMensaje(pagina))) { resultados.push(`${accion.nombre}: sin mensajes que probar`); break; }
    // Hay que llegar con un mensaje ABIERTO de verdad. Justo tras archivar, la lista puede
    // conservar un instante la fila del que ya no está: al pulsarla se refresca y queda sin
    // selección, y entonces la cinta está apagada con razón. Se reintenta hasta abrir uno.
    let abierto = false;
    for (let intento = 0; intento < 3 && !abierto; intento++) {
      const fila = pagina.locator('div[draggable="true"]').first();
      if (!(await fila.count())) { await asegurarUnMensaje(pagina); continue; }
      await fila.click().catch(() => {});
      await pagina.waitForTimeout(1800);
      abierto = !/Selecciona un mensaje para leerlo/.test(await pagina.locator('body').innerText());
    }
    if (!abierto) { resultados.push(`${accion.nombre}: ⚠ no se pudo abrir ningún mensaje`); continue; }

    const boton = pagina.getByRole('button', { name: accion.patron }).first();
    if (!(await boton.count()) || !(await boton.isVisible().catch(() => false))) {
      resultados.push(`${accion.nombre}: NO ESTÁ en la cinta`);
      continue;
    }
    if (await boton.isDisabled().catch(() => false)) {
      resultados.push(`${accion.nombre}: apagado con un mensaje abierto`);
      continue;
    }

    const antesVentanas = await pagina.locator('[role="dialog"], .compose-window').count();
    const antesTexto = (await pagina.locator('body').innerText()).length;
    const peticiones = [];
    const escucha = (r) => {
      if (r.method() !== 'GET' && r.url().includes('/api/')) peticiones.push(new URL(r.url()).pathname);
    };
    pagina.on('request', escucha);

    await boton.click({ timeout: 5000 }).catch(() => {});
    await pagina.waitForTimeout(1500);
    pagina.off('request', escucha);

    const despuesVentanas = await pagina.locator('[role="dialog"], .compose-window').count();
    const despuesTexto = (await pagina.locator('body').innerText()).length;
    const menus = await pagina.locator('[role="menu"], [role="menuitem"]').count();

    const senales = [];
    if (peticiones.length) senales.push(`pidió ${[...new Set(peticiones)].join(', ')}`);
    if (despuesVentanas > antesVentanas) senales.push('abrió una ventana');
    if (menus) senales.push(`desplegó un menú (${menus} opciones)`);
    if (Math.abs(despuesTexto - antesTexto) > 20) senales.push('cambió la pantalla');

    resultados.push(`${accion.nombre}: ${senales.length ? senales.join(' + ') : '⚠ NO PASÓ NADA'}`);

    // Dejar la pantalla como estaba para la siguiente acción.
    await pagina.keyboard.press('Escape');
    await pagina.waitForTimeout(500);
    if (despuesVentanas > antesVentanas) {
      const cerrar = pagina.getByRole('button', { name: /descartar|cerrar/i }).first();
      if (await cerrar.count()) await cerrar.click({ timeout: 3000 }).catch(() => {});
      await pagina.waitForTimeout(500);
      const confirmar = pagina.getByRole('button', { name: /^(descartar|no guardar|sí|si)$/i }).first();
      if (await confirmar.count()) await confirmar.click({ timeout: 3000 }).catch(() => {});
    }
    // Volver a tener un mensaje seleccionado (Archivar lo saca de la bandeja).
    if (!(await pagina.locator('div[draggable="true"]').first().count())) break;
    await pagina.waitForTimeout(400);
  }

  console.log('\n   --- acciones sobre un mensaje ---');
  for (const r of resultados) console.log('   ' + r);
  const graves = consola.filter((c) => !/401.*\/api\/chat|favicon|ResizeObserver/i.test(c));
  console.log('   errores de consola:', JSON.stringify(graves.slice(0, 5)));

  const mudas = resultados.filter((r) => /NO PASÓ NADA|NO ESTÁ|apagado/.test(r));
  expect(mudas, `acciones sin efecto visible: ${mudas.join(' | ')}`).toEqual([]);
});
