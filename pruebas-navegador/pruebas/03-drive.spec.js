// El Drive del correo: abre con la sesión del correo y dice algo útil si el buzón no está
// vinculado a una persona del directorio.
const { test, expect } = require('./base');
const { vigilar } = require('./apoyo');

test('el Drive acepta la sesión del correo', async ({ sesion }) => {
  const { pagina } = sesion;
  const ojo = vigilar(pagina);
  const r = await pagina.goto('/archivos-almacen', { waitUntil: 'domcontentloaded' });
  // Lo que NO puede pasar: mandar a la pantalla de entrada teniendo sesión válida.
  await expect(pagina).not.toHaveURL(/\/login|iniciar-sesion/i);
  console.log('   respuesta del Drive:', r.status());
  if (r.status() === 403) {
    console.log('   (buzón sin persona vinculada en el directorio: sale la página de ayuda)');
  }
  const fallidasAjenas = ojo.fallidas.filter((f) => !f.includes('/api/chat') && !f.includes('/archivos-almacen'));
  expect(fallidasAjenas, 'peticiones con error al abrir el Drive').toEqual([]);
});
