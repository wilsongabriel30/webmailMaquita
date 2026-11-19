// Direcciones de «Para» y «CC» sin nombres: lo que se envía al recuperar un correo.
// Ejecutar desde frontend/:  node --test tests/*.test.ts
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { direccionesDeCabecera } from '../src/lib/direccionesDeCabecera.ts';

test('quita el nombre y deja la dirección', () => {
  assert.deepEqual(
    direccionesDeCabecera('Mishel Pilicita <tecnicatth@example.org>, luis@example.org'),
    ['tecnicatth@example.org', 'luis@example.org'],
  );
});

test('un nombre entre comillas puede llevar comas y arrobas', () => {
  assert.deepEqual(
    direccionesDeCabecera('"Pérez, Ana (ana@otro.example)" <Ana@Example.org>'),
    ['ana@example.org'],
  );
});

test('junta varias cabeceras, sin repetir y en orden', () => {
  assert.deepEqual(
    direccionesDeCabecera('b@example.org, a@example.org', 'B <b@example.org>, c@example.org', undefined, ''),
    ['b@example.org', 'a@example.org', 'c@example.org'],
  );
});

test('sin direcciones devuelve una lista vacía', () => {
  assert.deepEqual(direccionesDeCabecera('', null, 'sin correo'), []);
});
