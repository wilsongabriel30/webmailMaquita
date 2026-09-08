// Lo que hace una persona con su correo: mirar carpetas, abrir el redactor, y que no haya ruido.
const { test, expect } = require('./base');
const { vigilar, abrirCorreo } = require('./apoyo');

test('la bandeja trae las carpetas de siempre', async ({ sesion }) => {
  const { pagina } = sesion;
  await abrirCorreo(pagina);
  for (const carpeta of [/entrada|recibidos|inbox/i, /enviados|sent/i, /papelera|trash/i]) {
    await expect(pagina.getByText(carpeta).first()).toBeVisible({ timeout: 20_000 });
  }
});

test('el redactor se abre y acepta un destinatario', async ({ sesion }) => {
  const { pagina } = sesion;
  await abrirCorreo(pagina);
  await pagina.getByRole('button', { name: /nuevo correo|redactar|escribir/i }).first().click();
  const para = pagina.locator('input[type="text"]:visible, input[type="email"]:visible').first();
  await expect(para).toBeVisible({ timeout: 20_000 });
  await para.fill('destino@ejemplo.org');
  await expect(para).toHaveValue('destino@ejemplo.org');
  // No se envía nada: la prueba termina aquí a propósito.
});

test('usar el correo no deja peticiones con error', async ({ sesion }) => {
  const { pagina } = sesion;
  const ojo = vigilar(pagina);
  await abrirCorreo(pagina);
  await pagina.waitForTimeout(4000);
  const delChat = ojo.fallidas.filter((f) => f.includes('/api/chat'));
  const resto = ojo.fallidas.filter((f) => !f.includes('/api/chat'));
  if (delChat.length) console.log('   ruido conocido del chat:', delChat.length, 'peticiones 401');
  expect(resto, 'peticiones con error mientras se usa el correo').toEqual([]);
});
