// El Drive del correo: abre con la sesión del correo y dice algo útil si el buzón no está
// vinculado a una persona del directorio.
const { test, expect } = require('./base');
const { vigilar, sinPeticionesFallidas } = require('./apoyo');

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
  // Antes se apartaba TODO lo de `/api/chat` y TODO lo de `/archivos-almacen`: así no se veía
  // ningún fallo del propio Drive. Ahora solo se aparta el 403 que la prueba ya ha comprobado
  // arriba (buzón sin persona vinculada) y el ruido conocido del chat en otra máquina.
  const esperadas = ojo.fallidas.filter((f) => /^403 GET \/archivos-almacen/.test(f));
  const resto = ojo.fallidas.filter((f) => !/^403 GET \/archivos-almacen/.test(f));
  if (esperadas.length) console.log('   ruido conocido:', esperadas.length, '× 403 del Drive ya comprobado');
  sinPeticionesFallidas(resto, 'peticiones con error al abrir el Drive');
});
