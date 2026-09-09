// Calendario, Contactos y Tareas, usados como los usa una persona: cambiar de vista, navegar,
// abrir fichas y empezar a crear cosas. Nada se guarda: los formularios se cierran sin más.
const path = require('path');
const fs = require('fs');
const { test, expect } = require('../pruebas/base');
const { apartarAvisos } = require('../pruebas/apoyo');
const { observar } = require('../exploracion/observador');
const { anotar, volcar } = require('../exploracion/informe');

const CAPTURAS = path.join(__dirname, '..', 'capturas', 'detallada');
fs.mkdirSync(CAPTURAS, { recursive: true });

test.describe.configure({ mode: 'serial' });

test('el calendario cambia de vista y navega por los meses', async ({ sesion }) => {
  test.setTimeout(600_000);
  const { pagina } = sesion;
  const ojo = observar(pagina);
  await pagina.goto('/webmail/calendar', { waitUntil: 'domcontentloaded' });
  await pagina.waitForTimeout(3000);
  await apartarAvisos(pagina);
  ojo.cosecha();

  for (const vista of [/^Día$|^Dia$/i, /semana laboral/i, /^Semana$/i, /^Mes$/i, /vista en dos paneles/i]) {
    const boton = pagina.getByRole('button', { name: vista }).first();
    if (!(await boton.count())) { anotar('baja', 'Calendario', `no está la vista ${vista}`, ''); continue; }
    await boton.click({ timeout: 5000 }).catch(() => {});
    await pagina.waitForTimeout(2000);
    const texto = (await pagina.locator('body').innerText()).trim();
    if (texto.length < 100) anotar('alta', 'Calendario', `la vista ${vista} deja la pantalla casi vacía`, '');
    const visto = ojo.cosecha();
    for (const e of visto.excepciones) anotar('alta', 'Calendario', `la vista ${vista} revienta la página`, e);
    for (const f of visto.fallidas) {
      anotar(/^5\d\d/.test(f) ? 'alta' : 'media', 'Calendario', `la vista ${vista} deja una petición fallida`, f);
    }
    console.log(`   vista ${vista}: abre`);
  }

  // Navegar hacia delante y volver a hoy.
  const siguiente = pagina.getByRole('button', { name: /siguiente|›|→/ }).first();
  const antesTitulo = (await pagina.locator('body').innerText()).slice(0, 200);
  if (await siguiente.count()) {
    await siguiente.click().catch(() => {});
    await pagina.waitForTimeout(1800);
    const despues = (await pagina.locator('body').innerText()).slice(0, 200);
    if (antesTitulo === despues) anotar('media', 'Calendario', 'avanzar de mes no cambia nada en pantalla', '');
  }
  const hoy = pagina.getByRole('button', { name: /^hoy$/i }).first();
  if (await hoy.count()) { await hoy.click().catch(() => {}); await pagina.waitForTimeout(1500); }
  await pagina.screenshot({ path: path.join(CAPTURAS, 'calendario.png') });
  volcar();
});

test('crear un evento: el formulario se abre entero (no se guarda)', async ({ sesion }) => {
  test.setTimeout(600_000);
  const { pagina } = sesion;
  const ojo = observar(pagina);
  await pagina.goto('/webmail/calendar', { waitUntil: 'domcontentloaded' });
  await pagina.waitForTimeout(2500);
  ojo.cosecha();

  const nuevo = pagina.getByRole('button', { name: /nuevo evento/i }).first();
  expect(await nuevo.count(), 'no se ve «Nuevo evento»').toBeGreaterThan(0);
  await nuevo.click({ timeout: 6000 }).catch(() => {});
  await pagina.waitForTimeout(2500);
  await pagina.screenshot({ path: path.join(CAPTURAS, 'calendario-evento-nuevo.png') });

  // Los campos se buscan por su texto de ayuda («Agregar título», «Requeridos: buscar
  // contacto»), no por el texto de la página: ese texto de ayuda NO aparece en `innerText`, y
  // buscarlo ahí daba por incompleto un formulario que está entero.
  for (const [que, hueco] of [
    ['dónde poner el título', /agregar t[íi]tulo|t[íi]tulo/i],
    ['a quién invitar', /requeridos|invitad|asistent/i],
  ]) {
    if (!(await pagina.getByPlaceholder(hueco).count())) {
      anotar('media', 'Calendario', `el formulario de evento no ofrece ${que}`, '');
    }
  }
  if (!(await pagina.getByRole('button', { name: /guardar/i }).count())) {
    anotar('alta', 'Calendario', 'el formulario de evento no ofrece con qué guardar', '');
  }
  const visto = ojo.cosecha();
  for (const e of visto.excepciones) anotar('alta', 'Calendario', 'abrir el formulario de evento revienta la página', e);

  await pagina.keyboard.press('Escape').catch(() => {});
  volcar();
});

test('contactos: la lista, la búsqueda y una ficha', async ({ sesion }) => {
  test.setTimeout(600_000);
  const { pagina } = sesion;
  const ojo = observar(pagina);
  await pagina.goto('/webmail/contacts', { waitUntil: 'domcontentloaded' });
  await pagina.waitForTimeout(3000);
  await apartarAvisos(pagina);
  ojo.cosecha();

  const texto = (await pagina.locator('body').innerText()).trim();
  console.log(`   contactos: ${texto.length} caracteres en pantalla`);

  // Abrir el primero que haya, si hay.
  const posibles = pagina.locator('[class*="contact"], li, tr').filter({ hasText: /@/ });
  if (await posibles.count()) {
    await posibles.first().click({ timeout: 5000 }).catch(() => {});
    await pagina.waitForTimeout(2000);
    await pagina.screenshot({ path: path.join(CAPTURAS, 'contactos-ficha.png') });
  } else {
    anotar('baja', 'Contactos', 'la agenda no tiene contactos que abrir', 'no se pudo evaluar la ficha');
  }

  const buscar = pagina.getByPlaceholder(/buscar/i).first();
  if (await buscar.count()) {
    await buscar.fill('a');
    await pagina.waitForTimeout(2500);
  }
  const visto = ojo.cosecha();
  for (const e of visto.excepciones) anotar('alta', 'Contactos', 'excepción al usar contactos', e);
  for (const f of visto.fallidas) {
    anotar(/^5\d\d/.test(f) ? 'alta' : 'media', 'Contactos', 'petición fallida al usar contactos', f);
  }
  volcar();
});

test('tareas: escribir una y ver las vistas (no se guarda)', async ({ sesion }) => {
  test.setTimeout(600_000);
  const { pagina } = sesion;
  const ojo = observar(pagina);
  await pagina.goto('/webmail/tasks', { waitUntil: 'domcontentloaded' });
  await pagina.waitForTimeout(3000);
  await apartarAvisos(pagina);
  ojo.cosecha();

  const caja = pagina.getByPlaceholder(/escriba aqu|nueva tarea|añadir/i).first();
  if (await caja.count()) {
    await caja.fill('Tarea de prueba (no se guarda)');
    const valor = await caja.inputValue().catch(() => '');
    if (!valor) anotar('alta', 'Tareas', 'la caja de nueva tarea no conserva lo escrito', '');
    else console.log('   la caja de nueva tarea acepta texto');
    await caja.fill('');
  } else {
    anotar('media', 'Tareas', 'no se encuentra dónde escribir una tarea nueva', '');
  }

  const visto = ojo.cosecha();
  for (const e of visto.excepciones) anotar('alta', 'Tareas', 'excepción en tareas', e);
  for (const f of visto.fallidas) {
    anotar(/^5\d\d/.test(f) ? 'alta' : 'media', 'Tareas', 'petición fallida en tareas', f);
  }
  await pagina.screenshot({ path: path.join(CAPTURAS, 'tareas.png') });
  volcar();
});
