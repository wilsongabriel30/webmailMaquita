import { test } from 'node:test';
import assert from 'node:assert/strict';
import { esCintaDeTelefono } from '../src/hooks/useCintaDeTelefono.ts';

test('una ventana angosta de escritorio conserva la cinta completa', () => {
  assert.equal(esCintaDeTelefono(680, false), false);   // ventana separada del mensaje
  assert.equal(esCintaDeTelefono(560, false), false);
  assert.equal(esCintaDeTelefono(1366, false), false);
});

test('un teléfono sigue con la barra reducida', () => {
  assert.equal(esCintaDeTelefono(390, true), true);
  assert.equal(esCintaDeTelefono(390, false), true);     // pantalla realmente pequeña
  assert.equal(esCintaDeTelefono(700, true), true);      // teléfono girado
});

test('una tableta o una pantalla táctil ancha usan la cinta de escritorio', () => {
  assert.equal(esCintaDeTelefono(800, true), false);
});
