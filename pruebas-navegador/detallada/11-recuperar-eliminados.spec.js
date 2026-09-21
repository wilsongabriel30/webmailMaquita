// La persona recupera sola un correo que borró y vació de la papelera, como hacía en Zimbra:
// clic derecho en Papelera -> Recuperar elementos eliminados.
const { test, expect } = require('../pruebas/base');
const { abrirCorreo } = require('../pruebas/apoyo');

test('recuperar elementos eliminados desde la Papelera', async ({ sesion }) => {
  test.setTimeout(300_000);
  const { pagina } = sesion;
  await abrirCorreo(pagina);

  // La opción vive en el menú de la Papelera, igual que en Zimbra.
  const papelera = pagina.locator('text=/^(Papelera|Trash|Eliminados)$/i').first();
  await papelera.click({ button: 'right' });
  await pagina.waitForTimeout(600);

  const opcion = pagina.locator('text=Recuperar elementos eliminados').first();
  await expect(opcion, 'la opción no aparece en el menú de la Papelera').toBeVisible();
  await opcion.click();
  await pagina.waitForTimeout(2500);

  // Se abre la ventana y dice de cuántos días habla.
  const titulo = pagina.locator('h2:has-text("Recuperar elementos eliminados")');
  await expect(titulo).toBeVisible();
  const aviso = await pagina.locator('text=/últimos 30 días/').first().isVisible().catch(() => false);
  console.log(`   ventana de 30 días visible: ${aviso ? 'sí' : 'no'}`);

  const filas = pagina.locator('button:has-text("Recuperar")');
  const cuantos = await filas.count();
  console.log(`   correos que puede recuperar: ${cuantos}`);

  if (cuantos > 0) {
    await filas.first().click();
    await pagina.waitForTimeout(2500);
    await expect(pagina.locator('text=Recuperado').first(), 'no confirmó la recuperación').toBeVisible();
    console.log('   recuperado y confirmado en pantalla');
  }

  // Y no hay forma de borrar DENTRO de la ventana: es la garantía de no perder correo.
  const ventana = pagina.locator('div:has(> div > h2:has-text("Recuperar elementos eliminados"))').last();
  const borrar = await ventana.locator('button:has-text("Eliminar"), button:has-text("Borrar")').count();
  expect(borrar, 'no debe haber ningún botón de borrar en esta ventana').toBe(0);
  console.log('   sin botones de borrar, como debe ser');
});
