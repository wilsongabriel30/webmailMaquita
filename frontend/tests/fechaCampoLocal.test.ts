// La hora que se propone en los campos «datetime-local» y «date» es la local, no la UTC.
// Ejecutar desde frontend/:  TZ=America/Guayaquil node --test tests/*.test.ts
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { paraCampoFecha, paraCampoFechaHora } from '../src/lib/fechaCampoLocal.ts';

test('el valor del campo es la hora local del equipo, con ceros a la izquierda', () => {
  const instante = new Date(2026, 0, 5, 7, 3);
  assert.equal(paraCampoFechaHora(instante), '2026-01-05T07:03');
  assert.equal(paraCampoFecha(instante), '2026-01-05');
});

test('ida y vuelta: lo que el campo devuelve se guarda como el mismo instante', () => {
  const instante = new Date(2026, 10, 15, 20, 58);
  assert.equal(new Date(paraCampoFechaHora(instante)).getTime(), instante.getTime());
});

test('«Programar envío» a las 19:58 de Ecuador propone las 20:58 del mismo día, no la 01:58 del siguiente', (t) => {
  if (new Date(2026, 10, 15, 12).getTimezoneOffset() !== 300) { t.skip('requiere TZ=America/Guayaquil'); return; }
  const ahora = new Date('2026-11-16T00:58:00Z'); // 19:58 del 15/11 en Ecuador
  const propuesta = new Date(ahora); propuesta.setHours(propuesta.getHours() + 1);
  assert.equal(paraCampoFechaHora(propuesta), '2026-11-15T20:58');
  assert.equal(propuesta.toISOString().slice(0, 16), '2026-11-16T01:58'); // lo que se proponía antes
  assert.equal(paraCampoFecha(ahora), '2026-11-15');
});
