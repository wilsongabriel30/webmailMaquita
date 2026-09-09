// Lo que la página hace por detrás mientras una persona la usa: errores de consola, excepciones
// y peticiones que fallan. Sin esto solo se ve la fachada.
const { separarRuido } = require('../pruebas/apoyo');

// El navegador escribe en la consola un «Failed to load resource» por CADA petición fallida, sin
// decir cuál. Las peticiones ya se miran una a una y con su ruta, así que ese eco duplicado solo
// sirve para ahogar la lista. Se aparta el eco, nunca un mensaje con contenido propio.
const ECO_DE_PETICION = /^Failed to load resource: the server responded with a status of \d+/;

// La cuenta de pruebas no está vinculada a una persona del directorio: el Almacén le niega el
// acceso con 403 y la interfaz lo cuenta. Es el comportamiento esperado con esa cuenta.
const ESPERADO_SIN_VINCULO = /\[Maquita\] api_error \{path: \/almacen\//;

/** Empieza a mirar una página. Devuelve un observador con `cosecha()` y `reiniciar()`. */
function observar(pagina) {
  let consola = [];
  let fallidas = [];
  let excepciones = [];

  pagina.on('console', (m) => {
    if (m.type() !== 'error') return;
    const texto = m.text();
    if (ECO_DE_PETICION.test(texto) || ESPERADO_SIN_VINCULO.test(texto)) return;
    consola.push(texto.slice(0, 300));
  });
  pagina.on('pageerror', (e) => excepciones.push(String(e).slice(0, 300)));
  pagina.on('response', (r) => {
    if (r.status() >= 400) {
      fallidas.push(`${r.status()} ${r.request().method()} ${new URL(r.url()).pathname}`);
    }
  });

  return {
    /** Lo visto desde la última siega, ya sin el ruido conocido. */
    cosecha() {
      const { reales, ruido } = separarRuido(fallidas);
      const visto = { consola: [...consola], excepciones: [...excepciones], fallidas: reales, ruido };
      consola = []; fallidas = []; excepciones = [];
      return visto;
    },
  };
}

/** ¿Esta cosecha trae algo que contar? */
function hayAlgo(visto) {
  return visto.consola.length || visto.excepciones.length || visto.fallidas.length;
}

module.exports = { observar, hayAlgo };
