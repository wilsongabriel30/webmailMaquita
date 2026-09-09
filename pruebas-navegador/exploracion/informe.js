// Recoge los hallazgos de la exploración y los deja en un fichero, para poder ordenarlos después
// por gravedad en lugar de leer el registro entero.
const fs = require('fs');
const path = require('path');

const DESTINO = process.env.INFORME_SALIDA
  || path.join(__dirname, '..', 'informe-exploracion.json');

const hallazgos = [];

/** Anota un hallazgo. `gravedad`: 'alta' | 'media' | 'baja'. */
function anotar(gravedad, seccion, que, detalle) {
  hallazgos.push({ gravedad, seccion, que, detalle, cuando: new Date().toISOString() });
  const marca = { alta: '!!', media: ' !', baja: ' ·' }[gravedad] || ' ·';
  console.log(`   ${marca} [${seccion}] ${que}${detalle ? ' — ' + detalle : ''}`);
}

/** Vuelca lo recogido. Se llama al final de la tanda. */
function volcar() {
  const orden = { alta: 0, media: 1, baja: 2 };
  hallazgos.sort((a, b) => orden[a.gravedad] - orden[b.gravedad]);
  fs.writeFileSync(DESTINO, JSON.stringify({ generado: new Date().toISOString(), hallazgos }, null, 2));
  console.log(`\n   Informe: ${hallazgos.length} hallazgos en ${DESTINO}`);
}

module.exports = { anotar, volcar, hallazgos };
