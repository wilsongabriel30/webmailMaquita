// «Informar» un correo: la pregunta dice que el remitente quedará bloqueado y el aviso lo confirma.
// Ejecutar desde frontend/:  node --test tests/*.test.ts
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { avisoDeInforme, preguntaDeInforme } from '../src/lib/textosInforme.ts';

test('la pregunta dice con claridad que se informa como suplantación y que el remitente quedará bloqueado', () => {
  const p = preguntaDeInforme('suplantacion');
  assert.match(p.titulo, /^¿Informar este correo como suplantación de identidad\?$/);
  const texto = p.texto.join(' ');
  assert.match(texto, /suplantación/);
  assert.match(texto, /El remitente quedará bloqueado/);
  assert.match(texto, /Remitentes bloqueados/);
  assert.match(p.aceptar, /bloquear remitente/);
  assert.equal(p.peligro, true);
});

test('con varios correos, la pregunta habla en plural', () => {
  const p = preguntaDeInforme('suplantacion', 3);
  assert.match(p.titulo, /estos 3 correos/);
  assert.match(p.texto.join(' '), /Sus remitentes quedarán bloqueados/);
});

test('marcar como no deseado también avisa del bloqueo', () => {
  const p = preguntaDeInforme('no-deseado');
  assert.match(p.titulo, /^¿Marcar este correo como no deseado\?$/);
  assert.match(p.texto.join(' '), /El remitente quedará bloqueado/);
});

test('el aviso de después nombra a quien el servidor bloqueó', () => {
  assert.equal(avisoDeInforme('suplantacion', 1, ['a@ejemplo.org']),
    'Informado como suplantación y movido a Correo no deseado. Remitente bloqueado: a@ejemplo.org.');
  assert.equal(avisoDeInforme('no-deseado', 2, ['a@ejemplo.org', 'b@ejemplo.org']),
    '2 correos movidos a Correo no deseado. Remitentes bloqueados: a@ejemplo.org, b@ejemplo.org.');
  assert.equal(avisoDeInforme('suplantacion', 9, ['a@x.org', 'b@x.org', 'c@x.org', 'd@x.org']),
    '9 correos informados como suplantación y movidos a Correo no deseado. 4 remitentes bloqueados.');
});

test('si el servidor no bloqueó a nadie (remitente de la casa o ya bloqueado), el aviso no lo afirma', () => {
  assert.equal(avisoDeInforme('no-deseado', 1, []), 'Movido a Correo no deseado.');
});
