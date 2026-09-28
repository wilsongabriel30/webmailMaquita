// Una persona administra su dominio de principio a fin. Las pruebas van en orden y comparten página.
const { test, expect } = require('@playwright/test');
const path = require('path');

const USUARIO = process.env.PORTAL_USUARIO;
const INICIAL = process.env.PORTAL_CLAVE;
const DOMINIO = process.env.PORTAL_DOMINIO;
const NUEVA = 'Zz9+' + Math.random().toString(36).slice(2, 12) + 'Qx';
const CAPTURAS = path.join(__dirname, '..', 'capturas', 'portal-dominio');
const MARCA = 'pw' + Date.now().toString(36);

test.describe.configure({ mode: 'serial' });
test.skip(!USUARIO || !INICIAL || !DOMINIO, 'Faltan PORTAL_USUARIO, PORTAL_CLAVE o PORTAL_DOMINIO');

let pagina;
const errores = [];
const ajenas = [];
let bytes = 0;
let dialogos = 0;

const captura = (nombre) => pagina.screenshot({ path: path.join(CAPTURAS, nombre + '.png'), fullPage: true });
const entrar = async (clave) => {
  await pagina.getByLabel('Usuario').fill(USUARIO);
  await pagina.getByLabel('Contraseña').fill(clave);
  await pagina.getByRole('button', { name: 'Entrar' }).click();
};

test.beforeAll(async ({ browser, baseURL }) => {
  const contexto = await browser.newContext({ ignoreHTTPSErrors: process.env.PRUEBAS_TLS_LAXA === '1', locale: 'es-EC' });
  pagina = await contexto.newPage();
  pagina.on('console', (m) => { if (m.type() === 'error' && !/status of (401|400|404|409)/.test(m.text())) errores.push(m.text()); });
  pagina.on('pageerror', (e) => errores.push(String(e)));
  pagina.on('dialog', async (d) => { dialogos++; await d.dismiss(); });
  pagina.on('request', (r) => { if (!r.url().startsWith(baseURL) && !r.url().startsWith('data:')) ajenas.push(r.url()); });
  pagina.on('response', async (r) => { const t = r.headers()['content-length']; if (t && !r.url().includes('/api/')) bytes += Number(t); });
});

test('la portada carga ligera, sin errores y sin pedir nada a terceros', async () => {
  const respuesta = await pagina.goto('/');
  await expect(pagina.getByRole('heading', { name: 'Administración de mi dominio' })).toBeVisible();
  const cabeceras = respuesta.headers();
  expect(cabeceras['content-security-policy']).toContain("default-src 'none'");
  expect(cabeceras['x-frame-options']).toBe('DENY');
  expect(ajenas).toEqual([]);
  expect(bytes).toBeLessThan(100 * 1024);
  await captura('01-entrada');
});

test('una clave equivocada se rechaza con un mensaje claro', async () => {
  await entrar('Equivocada-' + MARCA + '.A1');
  await expect(pagina.getByRole('alert')).toContainText('incorrectos');
});

test('la primera entrada obliga a cambiar la clave y no deja hacer nada más', async () => {
  await entrar(INICIAL);
  await expect(pagina.getByRole('heading', { name: 'Mi contraseña' })).toBeVisible();
  await expect(pagina.getByText('Es tu primera entrada')).toBeVisible();
  await expect(pagina.getByRole('link', { name: 'Cuentas' })).toHaveCount(0);
  await pagina.goto('/#cuentas');
  await expect(pagina.getByRole('heading', { name: 'Mi contraseña' })).toBeVisible();
  await captura('02-cambio-obligatorio');

  await pagina.getByLabel('Contraseña actual').fill(INICIAL);
  await pagina.getByLabel('Contraseña nueva', { exact: true }).fill(NUEVA);
  await pagina.getByLabel('Repite la contraseña nueva').fill(NUEVA + 'x');
  await pagina.getByRole('button', { name: 'Cambiar mi contraseña' }).click();
  await expect(pagina.getByRole('alert')).toContainText('no coinciden');

  await pagina.getByLabel('Contraseña nueva', { exact: true }).fill(NUEVA);
  await pagina.getByLabel('Repite la contraseña nueva').fill(NUEVA);
  await pagina.getByRole('button', { name: 'Cambiar mi contraseña' }).click();
  await expect(pagina.getByRole('button', { name: 'Entrar' })).toBeVisible();
});

test('con la clave nueva ve el resumen de su dominio y solo de ese', async () => {
  await entrar(NUEVA);
  await pagina.getByRole('link', { name: 'Resumen' }).click();
  await expect(pagina.getByRole('heading', { name: 'Resumen' })).toBeVisible();
  await expect(pagina.locator('.tarjetas .caja')).toHaveCount(1);
  await expect(pagina.locator('.tarjetas')).toContainText(DOMINIO);
  await captura('03-resumen');
});

test('crea una cuenta con clave generada, la busca, la edita y la desactiva', async () => {
  await pagina.getByRole('link', { name: 'Cuentas' }).click();
  await expect(pagina.getByRole('heading', { name: 'Cuentas de correo' })).toBeVisible();
  await expect(pagina.locator('main')).not.toContainText(/\bnull\b|\bundefined\b/);
  await pagina.getByRole('button', { name: 'Nueva cuenta' }).click();
  const ventana = pagina.getByRole('dialog');
  await ventana.getByLabel('Nombre de la cuenta').fill('ana.' + MARCA);
  await ventana.getByLabel('Nombre de la persona').fill('Ana de Prueba');
  await ventana.getByRole('button', { name: 'Generar una contraseña' }).click();
  expect((await ventana.getByLabel('Contraseña inicial').inputValue()).length).toBeGreaterThanOrEqual(16);
  await captura('04-nueva-cuenta');
  await ventana.getByRole('button', { name: 'Crear cuenta' }).click();
  await expect(pagina.getByRole('status')).toContainText('creada');

  const fila = pagina.getByRole('row', { name: new RegExp('ana\\.' + MARCA) });
  await expect(fila).toContainText('5 GB');
  await expect(fila).toContainText('Activa');

  await pagina.getByLabel('Buscar cuentas').fill('no-existe-' + MARCA);
  await expect(pagina.getByText('No hay cuentas que coincidan.')).toBeVisible();
  await pagina.getByLabel('Buscar cuentas').fill(MARCA);
  await expect(fila).toBeVisible();

  await fila.getByRole('button', { name: 'Editar' }).click();
  await pagina.getByRole('dialog').getByLabel('Nombre de la persona').fill('Ana Editada');
  await pagina.getByRole('dialog').getByRole('button', { name: 'Guardar' }).click();
  await expect(pagina.getByRole('row', { name: new RegExp('ana\\.' + MARCA) })).toContainText('Ana Editada');

  await pagina.getByRole('row', { name: new RegExp('ana\\.' + MARCA) }).getByRole('button', { name: 'Contraseña' }).click();
  await pagina.getByRole('dialog').getByLabel('Contraseña nueva').fill('123');
  await pagina.getByRole('dialog').getByLabel('Contraseña nueva').evaluate((e) => e.removeAttribute('minlength'));
  await pagina.getByRole('dialog').getByRole('button', { name: 'Cambiar contraseña' }).click();
  await expect(pagina.getByRole('dialog').getByRole('alert')).toContainText('al menos 10');
  await pagina.getByRole('dialog').getByRole('button', { name: 'Cancelar' }).click();

  await pagina.getByRole('row', { name: new RegExp('ana\\.' + MARCA) }).getByRole('button', { name: 'Desactivar' }).click();
  await pagina.getByRole('dialog').getByRole('button', { name: 'Desactivar' }).click();
  await expect(pagina.getByRole('row', { name: new RegExp('ana\\.' + MARCA) })).toContainText('Desactivada');
  await captura('05-cuentas');
});

test('un nombre con HTML se muestra como texto y no se ejecuta', async () => {
  await pagina.getByRole('button', { name: 'Nueva cuenta' }).click();
  const ventana = pagina.getByRole('dialog');
  await ventana.getByLabel('Nombre de la cuenta').fill('xss.' + MARCA);
  await ventana.getByLabel('Nombre de la persona').fill('<img src=x onerror=alert(1)><b>negrita</b>');
  await ventana.getByRole('button', { name: 'Generar una contraseña' }).click();
  await ventana.getByRole('button', { name: 'Crear cuenta' }).click();
  const fila = pagina.getByRole('row', { name: new RegExp('xss\\.' + MARCA) });
  await expect(fila).toContainText('<img src=x onerror=alert(1)>');
  await expect(pagina.locator('table img, table b')).toHaveCount(0);
  expect(dialogos).toBe(0);
});

test('alias: rechaza destinos de fuera y gestiona los propios', async () => {
  await pagina.getByRole('link', { name: 'Alias' }).click();
  await pagina.getByRole('button', { name: 'Nuevo alias' }).click();
  const ventana = pagina.getByRole('dialog');
  await ventana.getByLabel('Nombre del alias').fill('info.' + MARCA);
  await ventana.getByLabel('Entrega en').fill('alguien@gmail.com');
  await ventana.getByRole('button', { name: 'Crear alias' }).click();
  await expect(ventana.getByRole('alert')).toContainText('no es de tus dominios');
  await ventana.getByLabel('Entrega en').fill(`ana.${MARCA}@${DOMINIO}`);
  await ventana.getByRole('button', { name: 'Crear alias' }).click();
  await expect(pagina.getByRole('status')).toContainText('creado');
  const fila = pagina.getByRole('row', { name: new RegExp('info\\.' + MARCA) });
  await expect(fila).toContainText(`ana.${MARCA}@${DOMINIO}`);
  await captura('06-alias');
  await fila.getByRole('button', { name: 'Pausar' }).click();
  await expect(pagina.getByRole('row', { name: new RegExp('info\\.' + MARCA) })).toContainText('Pausado');
  await pagina.getByRole('row', { name: new RegExp('info\\.' + MARCA) }).getByRole('button', { name: 'Eliminar' }).click();
  await pagina.getByRole('dialog').getByRole('button', { name: 'Eliminar' }).click();
  await expect(pagina.getByRole('row', { name: new RegExp('info\\.' + MARCA) })).toHaveCount(0);
});

test('en un teléfono (360 px) no hay desplazamiento horizontal de la página', async () => {
  await pagina.setViewportSize({ width: 360, height: 740 });
  for (const seccion of ['resumen', 'cuentas', 'alias', 'clave']) {
    await pagina.goto('/#' + seccion);
    await expect(pagina.locator('main h1')).toBeVisible();
    const desborde = await pagina.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    expect(desborde, 'desborde en ' + seccion).toBeLessThanOrEqual(0);
    await captura('07-telefono-' + seccion);
  }
  await pagina.setViewportSize({ width: 1280, height: 800 });
});

test('al salir se borra la sesión y volver atrás no muestra nada', async () => {
  await pagina.goto('/#cuentas');
  await pagina.getByRole('button', { name: 'Salir' }).click();
  await expect(pagina.getByRole('button', { name: 'Entrar' })).toBeVisible();
  expect(await pagina.evaluate(() => sessionStorage.getItem('pd_ficha'))).toBeNull();
  await pagina.goBack();
  await expect(pagina.getByRole('heading', { name: 'Cuentas de correo' })).toHaveCount(0);
});

test('todo el recorrido sin errores en consola ni peticiones a terceros', async () => {
  expect(errores).toEqual([]);
  expect(ajenas).toEqual([]);
  expect(dialogos).toBe(0);
});
