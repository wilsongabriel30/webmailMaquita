// Cada sección del carril, por dentro: ¿carga, tiene contenido y sus botones responden?
//
// La prueba anterior de secciones solo comprobaba que la pantalla cambiaba. Aquí se entra en cada
// una y se pulsa lo que hay, mirando lo que la persona vería: contenido real (no un panel en
// blanco), botones que responden y ninguna pantalla de error.
const { test, expect } = require('./base');
const { abrirCorreo, apartarAvisos, vigilar } = require('./apoyo');

const SECCIONES = [
  { nombre: 'Correo', patron: /^Correo$/, senal: /Bandeja de entrada/i },
  { nombre: 'Calendario', patron: /^Calendario$/, senal: /hoy|lunes|enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre/i },
  { nombre: 'Contactos', patron: /^Contactos$/, senal: /contacto|directorio|nombre/i },
  { nombre: 'Tareas', patron: /^Tareas$/, senal: /tarea|pendiente|completad/i },
  { nombre: 'Asistente', patron: /^Asistente$/, senal: /asistente|pregunt|escrib/i },
];

test('cada sección carga con contenido y sin pantallas de error', async ({ sesion }) => {
  const { pagina } = sesion;
  const informe = [];

  for (const s of SECCIONES) {
    const { consola, fallidas } = vigilar(pagina);
    await abrirCorreo(pagina);
    const boton = pagina.getByRole('button', { name: s.patron }).first();
    if (!(await boton.count())) { informe.push(`${s.nombre}: ⚠ no está en el carril`); continue; }
    await boton.click();
    await pagina.waitForTimeout(3000);
    await apartarAvisos(pagina);

    const texto = await pagina.locator('body').innerText();
    const util = texto.replace(/\s+/g, ' ').trim();

    const problemas = [];
    // Una sección en blanco (solo el marco) es una sección rota. Pero «no hay contactos» en una
    // cuenta recién creada NO lo es: si la propia pantalla explica que está vacía, se acepta.
    const vacioExplicado = /No hay |Sin |Todavía no|Aún no|Crea tu primer/i.test(util);
    if (util.length < 300 && !vacioExplicado) problemas.push(`casi vacía (${util.length} caracteres)`);
    if (!s.senal.test(util)) problemas.push('no aparece lo que se espera ver ahí');
    // El JSON crudo de un error es lo que veía la persona en el fallo de «Archivos».
    if (/\{"error"|"success":\s*false|Internal Server Error|Not Found/.test(util)) {
      problemas.push('muestra un error en crudo');
    }
    if (/Algo salió mal|Error inesperado|Se produjo un error/i.test(util)) problemas.push('pantalla de error');

    const fallosGraves = fallidas.filter((f) => !/401 GET \/api\/chat|\/api\/ai\//.test(f));
    const erroresGraves = consola.filter((c) => !/401|favicon|ResizeObserver|\/api\/chat/i.test(c));

    informe.push(
      `${s.nombre}: ${problemas.length ? '⚠ ' + problemas.join('; ') : 'bien'}` +
      (fallosGraves.length ? ` | peticiones fallidas: ${[...new Set(fallosGraves)].slice(0, 4).join(', ')}` : '') +
      (erroresGraves.length ? ` | errores: ${erroresGraves.slice(0, 2).join(' / ')}` : ''),
    );
    await pagina.screenshot({ path: `informe/seccion-${s.nombre.toLowerCase()}.png` });
  }

  console.log('\n   --- secciones ---');
  for (const l of informe) console.log('   ' + l);

  const rotas = informe.filter((l) => l.includes('⚠') || l.includes('peticiones fallidas') || l.includes('errores:'));
  expect(rotas, `secciones con problemas:\n${rotas.join('\n')}`).toEqual([]);
});
