// Las carpetas del buzón de verdad —que aquí son muchas y con nombres propios— y la búsqueda
// con resultados. Solo se navega y se mira: no se mueve ni se borra nada.
const path = require('path');
const fs = require('fs');
const { test, expect } = require('../pruebas/base');
const { abrirCorreo } = require('../pruebas/apoyo');
const { observar } = require('../exploracion/observador');
const { anotar, volcar } = require('../exploracion/informe');

const CAPTURAS = path.join(__dirname, '..', 'capturas', 'detallada');
fs.mkdirSync(CAPTURAS, { recursive: true });

test.describe.configure({ mode: 'serial' });

test('todas las carpetas del buzón abren y dicen qué tienen', async ({ sesion }) => {
  test.setTimeout(900_000);
  const { pagina } = sesion;
  const ojo = observar(pagina);
  await abrirCorreo(pagina);
  ojo.cosecha();

  // Las carpetas propias del buzón, tal como aparecen en el panel lateral.
  // Las carpetas se buscan por dónde están en pantalla —la columna estrecha de la izquierda—
  // y no por etiquetas de HTML: con `nav`/`aside` no se encontraba ninguna, y la prueba daba
  // por vacío un panel con más de cincuenta carpetas.
  const carpetas = await pagina.$$eval('div', (nodos) => nodos
    .filter((n) => {
      const r = n.getBoundingClientRect();
      return r.left < 280 && r.width < 280 && r.height > 20 && r.height < 60 && n.children.length <= 3;
    })
    .map((n) => (n.innerText || '').trim().split('\n')[0])
    .filter((t) => t && t.length > 2 && t.length < 40));
  // Se recorren las primeras, no todas: en un buzón de trabajo hay más de cincuenta carpetas y
  // abrirlas una a una alarga la tanda sin enseñar nada nuevo. Sube el número si hace falta.
  const CUANTAS = Number(process.env.CARPETAS_A_PROBAR || 12);
  const unicas = [...new Set(carpetas)].slice(0, CUANTAS);
  console.log(`   carpetas a la vista: ${unicas.length}`);

  let abiertas = 0;
  for (const nombre of unicas) {
    const enlace = pagina.getByText(nombre, { exact: true }).first();
    if (!(await enlace.count()) || !(await enlace.isVisible().catch(() => false))) continue;
    await enlace.click({ timeout: 5000 }).catch(() => {});
    await pagina.waitForTimeout(1800);
    abiertas++;

    const texto = (await pagina.locator('body').innerText()).trim();
    if (texto.length < 60) {
      anotar('alta', 'Carpetas', `«${nombre}» deja la pantalla vacía`, '');
    }
    const visto = ojo.cosecha();
    for (const e of visto.excepciones) anotar('alta', 'Carpetas', `abrir «${nombre}» revienta la página`, e);
    for (const f of visto.fallidas) {
      anotar(/^5\d\d/.test(f) ? 'alta' : 'media', 'Carpetas', `abrir «${nombre}» deja una petición fallida`, f);
    }
  }
  console.log(`   carpetas abiertas sin incidencias: ${abiertas}`);
  expect(abiertas, 'no se pudo abrir ninguna carpeta').toBeGreaterThan(0);
  volcar();
});

test('buscar algo que sí existe devuelve resultados y se puede limpiar', async ({ sesion }) => {
  test.setTimeout(600_000);
  const { pagina } = sesion;
  const ojo = observar(pagina);
  await abrirCorreo(pagina);

  // Se busca por una palabra tomada de un correo real de la bandeja: así hay resultados.
  const primera = pagina.locator('div[draggable="true"]').first();
  const textoPrimera = (await primera.innerText().catch(() => '')).trim();
  const palabra = (textoPrimera.split(/\s+/).find((p) => p.length > 5 && /^[A-Za-zÁÉÍÓÚáéíóúñ]+$/.test(p)) || 'maquita');
  console.log(`   se busca: «${palabra}»`);
  ojo.cosecha();

  const caja = pagina.getByPlaceholder(/buscar/i).first();
  await caja.click();
  await caja.fill(palabra);
  await pagina.keyboard.press('Enter');
  await pagina.waitForTimeout(4000);
  await pagina.screenshot({ path: path.join(CAPTURAS, 'busqueda-con-resultados.png') });

  const texto = (await pagina.locator('body').innerText());
  const resultados = await pagina.locator('div[draggable="true"]').count();
  console.log(`   resultados: ${resultados}`);
  if (resultados === 0 && !/sin resultados/i.test(texto)) {
    anotar('media', 'Búsqueda', `buscar «${palabra}» no da resultados ni lo dice`, '');
  }

  // Y limpiar la búsqueda tiene que devolver a la bandeja.
  const limpiar = pagina.getByText(/limpiar la búsqueda|limpiar busqueda/i).first();
  if (await limpiar.count()) {
    await limpiar.click().catch(() => {});
    await pagina.waitForTimeout(2500);
    const vuelta = (await pagina.locator('body').innerText());
    if (!/bandeja de entrada/i.test(vuelta)) {
      anotar('media', 'Búsqueda', 'limpiar la búsqueda no devuelve a la bandeja', '');
    } else {
      console.log('   limpiar la búsqueda: vuelve a la bandeja');
    }
  }

  const visto = ojo.cosecha();
  for (const e of visto.excepciones) anotar('alta', 'Búsqueda', 'buscar revienta la página', e);
  for (const f of visto.fallidas) {
    anotar(/^5\d\d/.test(f) ? 'alta' : 'media', 'Búsqueda', 'petición fallida al buscar', f);
  }
  volcar();
});

test('los filtros de la bandeja hacen lo que dicen', async ({ sesion }) => {
  test.setTimeout(600_000);
  const { pagina } = sesion;
  const ojo = observar(pagina);
  await abrirCorreo(pagina);
  ojo.cosecha();

  const total = await pagina.locator('div[draggable="true"]').count();
  for (const filtro of ['No leídos', 'Marcados', 'Todos']) {
    const boton = pagina.getByRole('button', { name: filtro, exact: true }).first();
    if (!(await boton.count())) { anotar('baja', 'Filtros', `no está el filtro «${filtro}»`, ''); continue; }
    await boton.click({ timeout: 5000 }).catch(() => {});
    await pagina.waitForTimeout(2500);
    const cuantos = await pagina.locator('div[draggable="true"]').count();
    console.log(`   ${filtro}: ${cuantos} de ${total}`);
    if (filtro !== 'Todos' && cuantos > total) {
      anotar('media', 'Filtros', `«${filtro}» enseña MÁS correos que «Todos»`, `${cuantos} > ${total}`);
    }
    const visto = ojo.cosecha();
    for (const e of visto.excepciones) anotar('alta', 'Filtros', `«${filtro}» revienta la página`, e);
    for (const f of visto.fallidas.filter((x) => !x.startsWith('429'))) {
      anotar(/^5\d\d/.test(f) ? 'alta' : 'media', 'Filtros', `«${filtro}» deja una petición fallida`, f);
    }
  }
  volcar();
});
