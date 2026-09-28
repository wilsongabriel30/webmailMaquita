// Una persona administra su dominio de principio a fin. Las pruebas van en orden y comparten página.
const { test, expect } = require('@playwright/test');
const path = require('path');
const { codigo, pasoActual, png } = require('./ayudas');

const USUARIO = process.env.PORTAL_USUARIO;
const INICIAL = process.env.PORTAL_CLAVE;
const DOMINIO = process.env.PORTAL_DOMINIO;
const NUEVA = 'Zz9+' + Math.random().toString(36).slice(2, 12) + 'Qx';
const CAPTURAS = path.join(__dirname, '..', 'capturas', 'portal-dominio');
const MARCA = 'pw' + Date.now().toString(36);

test.describe.configure({ mode: 'serial' });
test.skip(!USUARIO || !INICIAL || !DOMINIO, 'Faltan PORTAL_USUARIO, PORTAL_CLAVE o PORTAL_DOMINIO');

let pagina;
let secreto = '';
let ultimoPaso = 0;
const errores = [];
const ajenas = [];
let bytes = 0;
let dialogos = 0;

const captura = (nombre) => pagina.screenshot({ path: path.join(CAPTURAS, nombre + '.png'), fullPage: true });
const fila = (texto) => pagina.getByRole('row', { name: new RegExp(texto.replace(/\./g, '\\.')) });
const entrar = async (clave) => {
  await pagina.getByLabel('Usuario').fill(USUARIO);
  await pagina.getByLabel('Contraseña').fill(clave);
  await pagina.getByRole('button', { name: 'Entrar' }).click();
};
// Un código vale una sola vez: se usa siempre un intervalo posterior al último gastado.
const codigoNuevo = () => { ultimoPaso = Math.max(pasoActual(), ultimoPaso + 1); return codigo(secreto, ultimoPaso); };

test.beforeAll(async ({ browser, baseURL }) => {
  const contexto = await browser.newContext({ ignoreHTTPSErrors: process.env.PRUEBAS_TLS_LAXA === '1', locale: 'es-EC' });
  pagina = await contexto.newPage();
  pagina.on('console', (m) => { if (m.type() === 'error' && !/status of (400|401|403|404|409)/.test(m.text())) errores.push(m.text()); });
  pagina.on('pageerror', (e) => errores.push(String(e)));
  pagina.on('dialog', async (d) => { dialogos++; await d.dismiss(); });
  pagina.on('request', (r) => { if (!r.url().startsWith(baseURL) && !/^(data|blob):/.test(r.url())) ajenas.push(r.url()); });
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

  await pagina.getByLabel('Contraseña actual').fill(INICIAL);
  await pagina.getByLabel('Contraseña nueva', { exact: true }).fill(NUEVA);
  await pagina.getByLabel('Repite la contraseña nueva').fill(NUEVA + 'x');
  await pagina.getByRole('button', { name: 'Cambiar mi contraseña' }).click();
  await expect(pagina.getByRole('alert')).toContainText('no coinciden');

  await pagina.getByLabel('Repite la contraseña nueva').fill(NUEVA);
  await pagina.getByRole('button', { name: 'Cambiar mi contraseña' }).click();
  await expect(pagina.getByRole('button', { name: 'Entrar' })).toBeVisible();
});

test('después exige el segundo factor: código QR, código equivocado y código correcto', async () => {
  await entrar(NUEVA);
  await expect(pagina.getByRole('heading', { name: 'Segundo factor' })).toBeVisible();
  await expect(pagina.getByRole('link', { name: 'Cuentas' })).toHaveCount(0);
  await pagina.goto('/#marca');
  await expect(pagina.getByRole('heading', { name: 'Segundo factor' })).toBeVisible();
  await pagina.getByRole('button', { name: 'Configurar ahora' }).click();
  const qr = pagina.getByRole('img', { name: /Código QR/ });
  await expect(qr).toBeVisible();
  expect(await qr.evaluate((i) => i.complete && i.naturalWidth > 0)).toBe(true);
  secreto = (await pagina.locator('code').first().innerText()).replace(/\s/g, '');
  expect(secreto.length).toBeGreaterThanOrEqual(16);
  await captura('02-segundo-factor');

  const bueno = codigoNuevo();
  await pagina.getByLabel('Código que muestra la aplicación').fill(bueno === '000000' ? '111111' : '000000');
  await pagina.getByRole('button', { name: 'Activar' }).click();
  await expect(pagina.getByRole('alert')).toContainText('no es correcto');
  await pagina.getByLabel('Código que muestra la aplicación').fill(bueno);
  await pagina.getByRole('button', { name: 'Activar' }).click();
  await expect(pagina.getByRole('link', { name: 'Cuentas' })).toBeVisible();
});

test('ve el resumen de su dominio y solo de ese', async () => {
  await pagina.getByRole('link', { name: 'Resumen' }).click();
  await expect(pagina.getByRole('heading', { name: 'Resumen' })).toBeVisible();
  await expect(pagina.locator('.tarjetas .caja')).toHaveCount(1);
  await expect(pagina.locator('.tarjetas')).toContainText(DOMINIO);
  await captura('03-resumen');
});

test('cuentas: crea con clave generada, busca, edita, reenvía y desactiva', async () => {
  await pagina.getByRole('link', { name: 'Cuentas' }).click();
  await expect(pagina.getByRole('heading', { name: 'Cuentas de correo' })).toBeVisible();
  await expect(pagina.locator('main')).not.toContainText(/\bnull\b|\bundefined\b/);
  for (const [local, nombre] of [['ana.' + MARCA, 'Ana de Prueba'], ['luis.' + MARCA, 'Luis de Prueba']]) {
    await pagina.getByRole('button', { name: 'Nueva cuenta' }).click();
    const ventana = pagina.getByRole('dialog');
    await ventana.getByLabel('Nombre de la cuenta').fill(local);
    await ventana.getByLabel('Nombre de la persona').fill(nombre);
    await ventana.getByRole('button', { name: 'Generar una contraseña' }).click();
    expect((await ventana.getByLabel('Contraseña inicial').inputValue()).length).toBeGreaterThanOrEqual(16);
    await ventana.getByRole('button', { name: 'Crear cuenta' }).click();
    await expect(pagina.getByRole('status')).toContainText('creada');
  }
  await expect(fila('ana.' + MARCA)).toContainText('5 GB');

  await pagina.getByLabel('Buscar cuentas').fill('no-existe-' + MARCA);
  await expect(pagina.getByText('No hay cuentas que coincidan.')).toBeVisible();
  await pagina.getByLabel('Buscar cuentas').fill('ana.' + MARCA);
  await expect(fila('ana.' + MARCA)).toBeVisible();
  await expect(fila('luis.' + MARCA)).toHaveCount(0);
  await pagina.getByLabel('Buscar cuentas').fill('');

  await fila('ana.' + MARCA).getByRole('button', { name: 'Editar' }).click();
  await pagina.getByRole('dialog').getByLabel('Nombre de la persona').fill('Ana Editada');
  await pagina.getByRole('dialog').getByRole('button', { name: 'Guardar' }).click();
  await expect(fila('ana.' + MARCA)).toContainText('Ana Editada');

  await fila('ana.' + MARCA).getByRole('button', { name: 'Reenvío' }).click();
  await pagina.getByRole('dialog').getByLabel('Reenviar también a').fill(`nadie.${MARCA}@${DOMINIO}`);
  await pagina.getByRole('dialog').getByRole('button', { name: 'Guardar' }).click();
  await expect(pagina.getByRole('dialog').getByRole('alert')).toContainText('No existe en tu dominio');
  await pagina.getByRole('dialog').getByLabel('Reenviar también a').fill(`luis.${MARCA}@${DOMINIO}`);
  await pagina.getByRole('dialog').getByRole('button', { name: 'Guardar' }).click();
  await expect(fila('ana.' + MARCA)).toContainText(`Reenvía a: luis.${MARCA}@${DOMINIO}`);

  await fila('ana.' + MARCA).getByRole('button', { name: 'Desactivar' }).click();
  await pagina.getByRole('dialog').getByRole('button', { name: 'Desactivar' }).click();
  await expect(fila('ana.' + MARCA)).toContainText('Desactivada');
  await captura('04-cuentas');
});

test('un nombre con HTML se muestra como texto y no se ejecuta', async () => {
  await pagina.getByRole('button', { name: 'Nueva cuenta' }).click();
  const ventana = pagina.getByRole('dialog');
  await ventana.getByLabel('Nombre de la cuenta').fill('xss.' + MARCA);
  await ventana.getByLabel('Nombre de la persona').fill('<img src=x onerror=alert(1)><b>negrita</b>');
  await ventana.getByRole('button', { name: 'Generar una contraseña' }).click();
  await ventana.getByRole('button', { name: 'Crear cuenta' }).click();
  await expect(fila('xss.' + MARCA)).toContainText('<img src=x onerror=alert(1)>');
  await expect(pagina.locator('table img, table b')).toHaveCount(0);
  expect(dialogos).toBe(0);
});

test('eliminar una cuenta se pide, no se hace: queda desactivada a la espera', async () => {
  await fila('xss.' + MARCA).getByRole('button', { name: 'Eliminar' }).click();
  await pagina.getByRole('dialog').getByLabel('Motivo (opcional)').fill('cuenta de prueba');
  await pagina.getByRole('dialog').getByRole('button', { name: 'Pedir eliminación' }).click();
  await expect(fila('xss.' + MARCA)).toContainText('Eliminación pedida');
  await expect(fila('xss.' + MARCA).getByRole('button')).toHaveCount(0);
});

test('alias: exige que el destino propio exista y gestiona los suyos', async () => {
  await pagina.getByRole('link', { name: 'Alias' }).click();
  await pagina.getByRole('button', { name: 'Nuevo alias' }).click();
  const ventana = pagina.getByRole('dialog');
  await ventana.getByLabel('Nombre del alias').fill('info.' + MARCA);
  await ventana.getByLabel('Entrega en').fill(`nadie.${MARCA}@${DOMINIO}`);
  await ventana.getByRole('button', { name: 'Crear alias' }).click();
  await expect(ventana.getByRole('alert')).toContainText('No existe en tu dominio');
  await ventana.getByLabel('Entrega en').fill(`luis.${MARCA}@${DOMINIO}`);
  await ventana.getByRole('button', { name: 'Crear alias' }).click();
  await expect(pagina.getByRole('status')).toContainText('creado');
  await expect(fila('info.' + MARCA)).toContainText(`luis.${MARCA}@${DOMINIO}`);
  await expect(pagina.locator('table')).not.toContainText('ana.' + MARCA);   // la cuenta con reenvío no es un alias
  await fila('info.' + MARCA).getByRole('button', { name: 'Pausar' }).click();
  await expect(fila('info.' + MARCA)).toContainText('Pausado');
  await fila('info.' + MARCA).getByRole('button', { name: 'Eliminar' }).click();
  await pagina.getByRole('dialog').getByRole('button', { name: 'Eliminar' }).click();
  await expect(fila('info.' + MARCA)).toHaveCount(0);
});

test('grupos: crea uno, agrega miembros y rechaza a los de fuera si está cerrado', async () => {
  await pagina.getByRole('link', { name: 'Grupos' }).click();
  await expect(pagina.getByRole('heading', { name: 'Grupos de distribución' })).toBeVisible();
  await pagina.getByRole('button', { name: 'Nuevo grupo' }).click();
  await pagina.getByRole('dialog').getByLabel('Dirección del grupo').fill('todos.' + MARCA);
  await pagina.getByRole('dialog').getByLabel('Nombre').fill('Todo el equipo');
  await pagina.getByRole('dialog').getByRole('button', { name: 'Crear grupo' }).click();
  const grupo = pagina.getByRole('region', { name: `todos.${MARCA}@${DOMINIO}` });
  await expect(grupo).toContainText('Sin miembros todavía');

  await grupo.getByRole('button', { name: 'Agregar miembro' }).click();
  await pagina.getByRole('dialog').getByLabel('Correo del miembro').fill('socio@example.org');
  await pagina.getByRole('dialog').getByRole('button', { name: 'Agregar' }).click();
  await expect(pagina.getByRole('dialog').getByRole('alert')).toContainText('no admite miembros de fuera');
  await pagina.getByRole('dialog').getByLabel('Correo del miembro').fill(`luis.${MARCA}@${DOMINIO}`);
  await pagina.getByRole('dialog').getByRole('button', { name: 'Agregar' }).click();
  await expect(pagina.getByRole('region', { name: `todos.${MARCA}@${DOMINIO}` })).toContainText(`luis.${MARCA}@${DOMINIO}`);
  await captura('05-grupos');
});

test('marca: cambia el nombre, sube un logo y rechaza lo que no es imagen', async () => {
  await pagina.getByRole('link', { name: 'Marca' }).click();
  await expect(pagina.getByRole('heading', { name: 'Marca', exact: true })).toBeVisible();
  const tarjeta = pagina.getByRole('region', { name: 'Marca de ' + DOMINIO });
  await tarjeta.getByLabel('Nombre de la organización').fill('Organización ' + MARCA);
  await tarjeta.getByRole('button', { name: 'Guardar textos y color' }).click();
  await expect(pagina.getByRole('status')).toContainText('guardada');
  await expect(pagina.getByRole('region', { name: 'Marca de ' + DOMINIO }).getByLabel('Nombre de la organización')).toHaveValue('Organización ' + MARCA);

  await pagina.getByLabel('Logo').setInputFiles({ name: 'logo.png', mimeType: 'image/png', buffer: Buffer.from('<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>') });
  await expect(pagina.getByRole('alert')).toContainText('Formato no admitido');
  await pagina.getByLabel('Logo').setInputFiles({ name: 'logo.png', mimeType: 'image/png', buffer: png(64, [15, 108, 189]) });
  await expect(pagina.getByRole('status')).toContainText('Logo actualizado');
  const imagen = pagina.getByRole('img', { name: 'Logo de ' + DOMINIO });
  await expect(imagen).toBeVisible();
  await expect.poll(() => imagen.evaluate((i) => i.naturalWidth)).toBe(64);
  await captura('06-marca');
  await pagina.getByRole('button', { name: 'Quitar logo' }).click();
  await expect(pagina.getByRole('status')).toContainText('quitado');
});

test('DNS: muestra el veredicto de su dominio', async () => {
  await pagina.getByRole('link', { name: 'DNS' }).click();
  const caja = pagina.getByRole('region', { name: 'DNS de ' + DOMINIO });
  await expect(caja).toContainText('MX — servidor de correo', { timeout: 30_000 });
  await expect(caja.locator('.marca')).toHaveCount(4);
});

test('en un teléfono (360 px) ninguna sección se desborda', async () => {
  await pagina.setViewportSize({ width: 360, height: 740 });
  for (const seccion of ['resumen', 'cuentas', 'alias', 'grupos', 'marca', 'dns', 'cuenta']) {
    await pagina.goto('/#' + seccion);
    await expect(pagina.locator('main h1').first()).toBeVisible();
    await pagina.waitForTimeout(300);
    const desborde = await pagina.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    expect(desborde, 'desborde en ' + seccion).toBeLessThanOrEqual(0);
    await captura('07-telefono-' + seccion);
  }
  await pagina.setViewportSize({ width: 1280, height: 800 });
});

test('al salir se borra la sesión; para volver hacen falta clave y código', async () => {
  await pagina.goto('/#cuentas');
  await pagina.getByRole('button', { name: 'Salir' }).click();
  await expect(pagina.getByRole('button', { name: 'Entrar' })).toBeVisible();
  expect(await pagina.evaluate(() => sessionStorage.getItem('pd_ficha'))).toBeNull();
  await pagina.goBack();
  await expect(pagina.getByRole('heading', { name: 'Cuentas de correo' })).toHaveCount(0);

  await pagina.goto('/');
  await entrar(NUEVA);
  const casilla = pagina.getByLabel('Código de 6 dígitos');
  await expect(casilla).toBeVisible();
  await expect(pagina.getByRole('link', { name: 'Cuentas' })).toHaveCount(0);
  await casilla.fill(codigo(secreto, ultimoPaso));          // el que ya se gastó al activar
  await pagina.getByRole('button', { name: 'Entrar' }).click();
  await expect(pagina.getByRole('alert')).toContainText('código no es correcto');
  await casilla.fill(codigoNuevo());
  await pagina.getByRole('button', { name: 'Entrar' }).click();
  await expect(pagina.getByRole('link', { name: 'Cuentas' })).toBeVisible();
});

test('todo el recorrido sin errores en consola ni peticiones a terceros', async () => {
  expect(errores).toEqual([]);
  expect(ajenas).toEqual([]);
  expect(dialogos).toBe(0);
});
