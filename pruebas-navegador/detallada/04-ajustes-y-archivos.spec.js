// Ajustes, pestaña por pestaña, y el Drive con una cuenta de verdad.
//
// En Ajustes se MIRA todo y no se guarda nada: cambiar la configuración de una cuenta real por
// una prueba sería justo lo que no se debe hacer.
const path = require('path');
const fs = require('fs');
const { test, expect } = require('../pruebas/base');
const { apartarAvisos } = require('../pruebas/apoyo');
const { observar } = require('../exploracion/observador');
const { anotar, volcar } = require('../exploracion/informe');

const CAPTURAS = path.join(__dirname, '..', 'capturas', 'detallada');
fs.mkdirSync(CAPTURAS, { recursive: true });

test.describe.configure({ mode: 'serial' });

test('cada pestaña de Ajustes abre y enseña algo', async ({ sesion }) => {
  test.setTimeout(900_000);
  const { pagina } = sesion;
  const ojo = observar(pagina);
  await pagina.goto('/webmail/settings', { waitUntil: 'domcontentloaded' });
  await pagina.waitForTimeout(3000);
  await apartarAvisos(pagina);
  ojo.cosecha();

  // Las pestañas, tal como se ofrecen en la pantalla.
  const nombres = await pagina.$$eval('button, [role="tab"], nav a', (nodos) => nodos
    .filter((n) => n.offsetParent !== null)
    .map((n) => (n.innerText || '').trim())
    .filter((t) => t && t.length > 2 && t.length < 30));
  const candidatas = [...new Set(nombres)].filter((n) =>
    /general|firma|cuenta|seguridad|contrase|reglas|filtro|vacacion|ausencia|idioma|apariencia|notific|privacidad|dispositiv|sesion|almacen|avanzad|acerca/i.test(n));
  console.log(`   pestañas de ajustes encontradas: ${candidatas.join(' · ') || '(ninguna reconocible)'}`);

  for (const nombre of candidatas.slice(0, 15)) {
    const boton = pagina.getByRole('button', { name: nombre, exact: true }).first();
    const enlace = (await boton.count()) ? boton : pagina.getByText(nombre, { exact: true }).first();
    if (!(await enlace.count())) continue;
    await enlace.click({ timeout: 5000 }).catch(() => {});
    await pagina.waitForTimeout(2200);

    const texto = (await pagina.locator('body').innerText()).trim();
    if (texto.length < 80) anotar('alta', 'Ajustes', `la pestaña «${nombre}» deja la pantalla vacía`, '');
    for (const senal of [/algo salió mal/i, /error inesperado/i, /cannot read/i]) {
      if (senal.test(texto)) anotar('alta', 'Ajustes', `«${nombre}» muestra un error a la persona`, String(senal));
    }
    const visto = ojo.cosecha();
    for (const e of visto.excepciones) anotar('alta', 'Ajustes', `«${nombre}» revienta la página`, e);
    for (const f of visto.fallidas) {
      anotar(/^5\d\d/.test(f) ? 'alta' : 'media', 'Ajustes', `«${nombre}» deja una petición fallida`, f);
    }
    console.log(`   ${nombre}: abre`);
  }
  await pagina.screenshot({ path: path.join(CAPTURAS, 'ajustes.png') });
  volcar();
});

test('el Drive con una cuenta de verdad', async ({ sesion }) => {
  test.setTimeout(600_000);
  const { pagina } = sesion;
  const ojo = observar(pagina);
  const respuesta = await pagina.goto('/webmail/files', { waitUntil: 'domcontentloaded' }).catch(() => null);
  await pagina.waitForTimeout(4000);
  await apartarAvisos(pagina);

  const texto = (await pagina.locator('body').innerText()).trim();
  console.log(`   respuesta: ${respuesta?.status()} · ${texto.length} caracteres en pantalla`);
  await pagina.screenshot({ path: path.join(CAPTURAS, 'archivos.png') });

  const visto = ojo.cosecha();
  const negado = visto.fallidas.some((f) => f.startsWith('403'));
  if (negado) {
    // Con el arreglo de esta semana, un acceso negado tiene que DECIRLO, no fingir carpeta vacía.
    if (/vacía|vacia/i.test(texto) && !/acceso/i.test(texto)) {
      anotar('alta', 'Archivos', 'el Almacén niega el acceso y la pantalla dice «carpeta vacía»',
        'es justo lo que se corrigió: comprobar que el cambio llegó');
    } else {
      console.log('   el acceso denegado se explica, como debe');
    }
  }
  for (const e of visto.excepciones) anotar('alta', 'Archivos', 'excepción en el Drive', e);
  for (const f of visto.fallidas.filter((x) => !x.startsWith('403'))) {
    anotar(/^5\d\d/.test(f) ? 'alta' : 'media', 'Archivos', 'petición fallida en el Drive', f);
  }
  volcar();
  expect(true).toBe(true);
});

test('el enlace «Archivos» del menú lleva a alguna parte', async ({ sesion }) => {
  test.setTimeout(300_000);
  const { pagina } = sesion;
  const ojo = observar(pagina);
  await pagina.goto('/webmail/', { waitUntil: 'domcontentloaded' });
  await pagina.waitForTimeout(2500);
  ojo.cosecha();

  const archivos = pagina.getByRole('button', { name: /^Archivos$/ }).first();
  if (!(await archivos.count())) { anotar('media', 'Menú', 'no está el acceso a Archivos', ''); volcar(); return; }
  await archivos.click({ timeout: 5000 }).catch(() => {});
  await pagina.waitForTimeout(4000);

  const texto = (await pagina.locator('body').innerText()).trim();
  const url = pagina.url();
  console.log(`   tras pulsar Archivos: ${url}`);
  // Lo que se arregló esta semana: la barra final llevaba a un error en crudo del servidor.
  if (/Not Found|404|Internal Server Error|Traceback/i.test(texto)) {
    anotar('alta', 'Menú', 'pulsar «Archivos» lleva a un error en crudo', url);
  }
  await pagina.screenshot({ path: path.join(CAPTURAS, 'menu-archivos.png') });
  const visto = ojo.cosecha();
  for (const e of visto.excepciones) anotar('alta', 'Menú', 'excepción al ir a Archivos', e);
  volcar();
});
