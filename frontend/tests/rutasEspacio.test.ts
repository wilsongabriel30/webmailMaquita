// Pruebas de la lógica de rutas por espacio del Drive.
// Ejecutar desde frontend/:  node --test tests/*.test.ts
// (Node 22.18+ ejecuta TypeScript sin compilar; no hace falta instalar nada.)
import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  carpetaInicialSelector, espacioDeRuta, esListaDeUnidades, migasDelEspacio, mismoEspacio,
  motivoDestinoInvalido, normalizarRuta, padreDentroDelEspacio, rutaDestino,
} from '../src/components/files/rutasEspacio.ts';

// Lo que hacía el diálogo antiguo: arrancar en «/» y unir la carpeta elegida con el nombre.
const destinoAntiguo = (carpetaElegida: string, nombre: string) =>
  (carpetaElegida === '/' ? '' : carpetaElegida) + '/' + nombre;

test('reproduce el fallo: dentro de una unidad, el diálogo antiguo perdía el prefijo', () => {
  // El diálogo antiguo solo listaba «Mis archivos»: la carpeta «B» que se elegía era la PROPIA.
  const destino = destinoAntiguo('/B', 'informe.txt');
  assert.equal(espacioDeRuta(destino).tipo, 'propio');
  assert.equal(mismoEspacio('/unidades/5/A/informe.txt', destino), false);
});

test('el diálogo arranca en la carpeta actual de la unidad y el destino conserva el prefijo', () => {
  const inicio = carpetaInicialSelector('/unidades/5/A', true);
  assert.equal(inicio, '/unidades/5/A');
  const destino = rutaDestino('/unidades/5/B', 'informe.txt');
  assert.equal(destino, '/unidades/5/B/informe.txt');
  assert.ok(mismoEspacio('/unidades/5/A/informe.txt', destino));
});

test('en el espacio propio el diálogo sigue arrancando en la raíz', () => {
  assert.equal(carpetaInicialSelector('/Proyectos/2026', true), '/');
  assert.equal(carpetaInicialSelector('/unidades/5/A', false), '/');   // favoritos, búsqueda…
});

test('espacioDeRuta reconoce unidades y no confunde nombres parecidos', () => {
  assert.deepEqual(espacioDeRuta('/unidades/12/x'), { tipo: 'unidad', raiz: '/unidades/12', unidadId: '12' });
  assert.deepEqual(espacioDeRuta('/unidades/12'), { tipo: 'unidad', raiz: '/unidades/12', unidadId: '12' });
  assert.equal(espacioDeRuta('/unidades/12abc').tipo, 'propio');
  assert.equal(espacioDeRuta('/unidadesX/1').tipo, 'propio');
  assert.equal(espacioDeRuta('/').raiz, '/');
});

test('normalizarRuta limpia barras sobrantes', () => {
  assert.equal(normalizarRuta(''), '/');
  assert.equal(normalizarRuta('//a///b/'), '/a/b');
  assert.equal(rutaDestino('/', 'x.txt'), '/x.txt');
});

test('subir nunca pasa de la raíz del espacio', () => {
  assert.equal(padreDentroDelEspacio('/unidades/5/A/B'), '/unidades/5/A');
  assert.equal(padreDentroDelEspacio('/unidades/5/A'), '/unidades/5');
  assert.equal(padreDentroDelEspacio('/unidades/5'), null);
  assert.equal(padreDentroDelEspacio('/A'), '/');
  assert.equal(padreDentroDelEspacio('/'), null);
});

test('las migas empiezan en la raíz del espacio y van prefijadas', () => {
  assert.deepEqual(migasDelEspacio('/unidades/5/A/B'), [
    { ruta: '/unidades/5', parte: '5', esRaiz: true },
    { ruta: '/unidades/5/A', parte: 'A', esRaiz: false },
    { ruta: '/unidades/5/A/B', parte: 'B', esRaiz: false },
  ]);
  assert.deepEqual(migasDelEspacio('/Docs'), [
    { ruta: '/', parte: '', esRaiz: true },
    { ruta: '/Docs', parte: 'Docs', esRaiz: false },
  ]);
});

test('destinos no válidos', () => {
  assert.equal(motivoDestinoInvalido('/A/x.txt', '/A', 'x.txt'), 'Ya está en esa carpeta');
  assert.match(motivoDestinoInvalido('/A', '/A/B', 'A') || '', /dentro de sí misma/);
  assert.match(motivoDestinoInvalido('/A', '/A', 'A') || '', /Ya está|dentro de sí misma/);
  assert.ok(esListaDeUnidades('/unidades/'));
  assert.ok(motivoDestinoInvalido('/A/x.txt', '/unidades', 'x.txt'));
  assert.equal(motivoDestinoInvalido('/unidades/5/A/x.txt', '/unidades/5/B', 'x.txt'), null);
  assert.equal(motivoDestinoInvalido('/AB/x.txt', '/A', 'x.txt'), null);   // «/A» no contiene a «/AB»
});
