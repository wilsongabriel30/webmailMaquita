// Ctrl+clic en la lista de correos: suma o quita de la selección.
// Ejecutar desde frontend/:  node --test tests/*.test.ts
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { seleccionTrasCtrlClic } from '../src/lib/seleccionConClic.ts';

const lista = (s: Set<number>) => Array.from(s).sort((a, b) => a - b);

test('con correos ya seleccionados, Ctrl+clic en otra fila la suma', () => {
  assert.deepEqual(lista(seleccionTrasCtrlClic(new Set([5, 7]), 9, null)), [5, 7, 9]);
  assert.deepEqual(lista(seleccionTrasCtrlClic(new Set([5, 7]), 9, 5)), [5, 7, 9]);
});

test('Ctrl+clic sobre una fila ya seleccionada la quita', () => {
  assert.deepEqual(lista(seleccionTrasCtrlClic(new Set([5, 7]), 7, 5)), [5]);
});

test('con un correo abierto y nada marcado, Ctrl+clic en otra fila selecciona los dos', () => {
  assert.deepEqual(lista(seleccionTrasCtrlClic(new Set(), 9, 5)), [5, 9]);
});

test('sin correo abierto, o sobre el mismo correo abierto, selecciona solo la fila pulsada', () => {
  assert.deepEqual(lista(seleccionTrasCtrlClic(new Set(), 9, null)), [9]);
  assert.deepEqual(lista(seleccionTrasCtrlClic(new Set(), 9, 9)), [9]);
});

test('no modifica la selección recibida', () => {
  const antes = new Set([5]);
  seleccionTrasCtrlClic(antes, 9, null);
  assert.deepEqual(lista(antes), [5]);
});
