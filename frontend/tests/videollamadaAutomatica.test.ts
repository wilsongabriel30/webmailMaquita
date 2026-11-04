// Videollamada automática al invitar (reuniones del correo ⇄ Meet Maquita, 04/11/2026).
// Ejecutar desde frontend/:  node --test tests/*.test.ts
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { debeEncenderVideollamada } from '../src/components/calendar/videollamadaAutomatica.ts';

test('evento nuevo con el primer invitado: se enciende', () => {
  assert.equal(debeEncenderVideollamada(true, 1, '', false), true);
});

test('sin invitados no se enciende (una cita personal no lleva sala)', () => {
  assert.equal(debeEncenderVideollamada(true, 0, '', false), false);
});

test('al editar un evento existente no se toca', () => {
  assert.equal(debeEncenderVideollamada(false, 3, '', false), false);
});

test('si la persona ya decidió (la apagó o ya se encendió) se respeta', () => {
  assert.equal(debeEncenderVideollamada(true, 2, '', true), false);
});

test('si el lugar ya trae un enlace de otra plataforma no se crea otra sala', () => {
  assert.equal(debeEncenderVideollamada(true, 1, 'https://zoom.us/j/123', false), false);
  assert.equal(debeEncenderVideollamada(true, 1, 'Sala de reuniones, piso 2', false), true);
});

test('en un evento que se repite no se enciende (la sala tiene una sola fecha)', () => {
  assert.equal(debeEncenderVideollamada(true, 2, '', false, true), false);
});
