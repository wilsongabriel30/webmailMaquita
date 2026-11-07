// Panel lateral del asistente de IA (components/asistente-lateral, 27/10/2026):
// se abre desde la barra superior, resume el correo abierto, responde preguntas y se cierra con Esc.
const { test, expect } = require('./base');
const { vigilar, abrirCorreo, asegurarUnMensaje, sinPeticionesFallidas } = require('./apoyo');

test('el panel del asistente se abre, resume, responde y se cierra', async ({ sesion }) => {
  test.setTimeout(240_000);
  const { pagina } = sesion;
  const ojo = vigilar(pagina);
  await abrirCorreo(pagina);

  // Si quedó abierto de una prueba anterior, se cierra primero para empezar igual siempre.
  const panel = pagina.getByRole('complementary', { name: /asistente de ia/i });
  if (await panel.isVisible()) await pagina.keyboard.press('Escape');

  await pagina.getByRole('button', { name: /^asistente$/i }).first().click();
  await expect(panel).toBeVisible({ timeout: 10_000 });
  await expect(panel.getByText(/pregúntale a tu correo/i).first()).toBeVisible();
  await pagina.screenshot({ path: 'informe/asistente-abierto.png' });

  // Resumir el correo abierto.
  if (await asegurarUnMensaje(pagina)) {
    await pagina.locator('div[draggable="true"]').first().click();
    const resumir = panel.getByRole('button', { name: /resumir este correo/i });
    await expect(resumir).toBeVisible({ timeout: 15_000 });
    await resumir.click();
    await expect(panel.getByText(/^resumen$/i)).toBeVisible({ timeout: 90_000 });
    await pagina.screenshot({ path: 'informe/asistente-resumen.png' });
  }

  // Una pregunta sobre la bandeja (si el buzón aún no está preparado, el panel lo dice).
  const caja = panel.getByRole('textbox', { name: /pregunta para el asistente/i });
  if (await caja.isVisible()) {
    await caja.fill('¿Qué tengo pendiente?');
    await caja.press('Enter');
    await expect(panel.getByText(/revisando tus correos/i)).toBeHidden({ timeout: 90_000 });
    await pagina.screenshot({ path: 'informe/asistente-pregunta.png' });

    // Las fuentes abren el correo con un clic, también desde otra sección.
    const fuente = panel.locator('button[title^="Abrir:"]').first();
    if (await fuente.count()) {
      const asunto = ((await fuente.getAttribute('title')) || '').replace(/^Abrir: /, '').split(' — ')[0];
      await pagina.goto('/webmail/calendar').catch(() => {});
      if (!(await panel.isVisible())) await pagina.getByRole('button', { name: /^asistente$/i }).first().click();
      await panel.locator('button[title^="Abrir:"]').first().click().catch(async () => {
        // Tras navegar, la conversación (en memoria) puede haberse perdido: se vuelve a preguntar.
        await caja.fill('¿Qué tengo pendiente?');
        await caja.press('Enter');
        await panel.locator('button[title^="Abrir:"]').first().click({ timeout: 90_000 });
      });
      await expect(pagina.getByRole('heading', { name: asunto }).first()).toBeVisible({ timeout: 20_000 });
      await pagina.screenshot({ path: 'informe/asistente-fuente-abierta.png' });
    }
  }

  await pagina.keyboard.press('Escape');
  await expect(panel).toBeHidden();
  sinPeticionesFallidas(ojo.fallidas, 'panel del asistente');
});
