// Dónde va el rótulo «Coincidencias en el contenido del correo» en los resultados de búsqueda.
// Ejecutar desde frontend/:  node --test tests/*.test.ts
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { rotuloDeNiveles } from '../src/lib/nivelesBusqueda.ts';

const m = (uid: number, coincidencia?: 'exacta' | 'contenido') => ({ uid, coincidencia });

test('sin datos del servidor no hay rótulo: la lista queda como siempre', () => {
  assert.equal(rotuloDeNiveles([m(3), m(2), m(1)], [m(3), m(2), m(1)]), null);
  assert.equal(rotuloDeNiveles([], []), null);
});

test('el rótulo va antes del primer correo que solo coincide en el contenido', () => {
  const lista = [m(9, 'exacta'), m(4, 'exacta'), m(8, 'contenido'), m(7, 'contenido')];
  assert.deepEqual(rotuloDeNiveles(lista, lista), { uid: 8, sinExactas: false });
});

test('todo exacto: sin rótulo', () => {
  const lista = [m(9, 'exacta'), m(4, 'exacta')];
  assert.equal(rotuloDeNiveles(lista, lista), null);
});

test('ninguna exacta: el rótulo abre la lista y lo dice', () => {
  const lista = [m(8, 'contenido'), m(7, 'contenido')];
  assert.deepEqual(rotuloDeNiveles(lista, lista), { uid: 8, sinExactas: true });
});

test('con otro orden (o una chincheta) los niveles se mezclan: sin rótulo', () => {
  const lista = [m(8, 'contenido'), m(9, 'exacta'), m(7, 'contenido')];
  assert.equal(rotuloDeNiveles(lista, lista), null);
});

test('una pestaña que solo muestra contenido no dice «sin exactas» si las hay en la otra', () => {
  const cargados = [m(9, 'exacta'), m(8, 'contenido'), m(7, 'contenido')];
  assert.deepEqual(rotuloDeNiveles(cargados.slice(1), cargados), { uid: 8, sinExactas: false });
});
